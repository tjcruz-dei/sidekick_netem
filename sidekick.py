#!/usr/bin/python3

#
#####MACOS !/Users/tjcruz/Applications/Anaconda3/anaconda3/bin/python
#
#
# EXPERIMENT SCHEDULER 
# PRELOAD VERSION 4.0 - DAEMON LOWCPU NOPOLLING,MQTT, Multiple instances
# requires python-daemon, patho-mqtt, argparse
# TODO: workingdirectory daemon;
# PYTHONPATH incluir diretoria dos scripts
# Reloadconfig; JSON from MQTT
#

import argparse
import syslog,sys,shlex
import sched,time
import daemon
import multiprocessing
import subprocess
import random
from paho.mqtt import client as mqtt_client
import json_parser

#USER CONFIGURARIONS
PATH="<deployment path>"
broker = 'MQTT BROKER'
port = 1883
topic_send = "netem/status"
topic_recv = "netem/scheduler"

# generate client ID with pub prefix randomly
client_id = f'python-mqtt-{random.randint(0, 100)}'
# username = 'emqx'
# password = 'public'

schedTask={}
logMode=False

#MQTT Connect
def connect_mqtt() -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            debug_report("Connected to MQTT Broker!")
            subscribe(client)
        else:
            debug_report("Failed to connect, return code %d\n", rc)

    def on_disconnect(client, userdata, rc):
        if rc != 0:
           debug_report("Unexpected disconnection.")

    client = mqtt_client.Client(client_id)
    #client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect(broker, port)
    return client

#MQTT Pub
def publish(msg):
    result = client.publish(topic_send, msg)
    # result: [0, 1]
    status = result[0]
    if (status!=0):
        debug_report(f"Failed to send message to topic {topic_send}")

#MQTT Subscribe
def subscribe(client: mqtt_client):
    def on_message(client, userdata, msg):
        #print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
        schedule(msg.payload.decode())

    client.subscribe(topic_recv)
    client.on_message = on_message

#Shaper trigger
def shaper_on(group):
	ctime=time.time()
	json_parser.test_mode(json_parser.group_cmds[group]['test_cmds'])
	etime=time.time()
	debug_report("ON CURRENT EPOCH "+group+":"+str(ctime)+":"+str(etime))
	debug_report("ON CURRENT TIME "+group+":"+str(time.gmtime(ctime)))

#Shaper off
def shaper_off(group):
	ctime=time.time()
	json_parser.norm_mode(json_parser.group_cmds[group]['nom_cmds'])
	etime=time.time()
	debug_report("OFF CURRENT EPOCH "+group+":"+str(ctime)+":"+str(etime))
	debug_report("OFF CURRENT TIME "+group+":"+str(time.gmtime(ctime)))

#Schedule on/off
def pschedule(start,duration,scheduler,group):
	eventon=scheduler.enterabs(start,1,shaper_on,argument=(group,))
	eventoff=scheduler.enterabs(start+duration,1,shaper_off,argument=(group,))
	scheduler.run()
	debug_report("End scheduled batch for group "+group+":"+str(time.time()))

#Sanity and consistency checks
def check_sanity(msg):
        parsemsg=msg.split(':')
        if not(len(parsemsg)==3): 
                return False
        try:
                group=parsemsg[0]
                start=float(parsemsg[1])
                duration=float(parsemsg[2])
        except:
                debug_report("Start or duration values invalid")
                publish("Start or duration values invalid")
                return False

        if ((start<time.time()) or (duration<5) or ((start+duration)<time.time()) or ((start+duration)>2147483647)):
                debug_report("Invalid value, scheduling in the past or with a small time window")
                publish("Invalid value, scheduling in the past or with a small time window")
                return False

        if (not json_parser.group_exist(group)):
                debug_report("Invalid group")
                publish("Invalid group")
                return False

        return True

#Arbitrary command execution
def os_executor(cmd):
	#process=subprocess.run(["ls","-all"],stdout=subprocess.PIPE,universal_newlines=True)
	process=subprocess.run(shlex.split(cmd),stdout=subprocess.PIPE,universal_newlines=True)
	#file=open("/tmp/out.txt","w")
	debug_report(process.stdout)
	#debug_report(process.stderr)
	#file.close
	return(process.stdout)

#Parameter removal
def param_removal(CMD,msg):
                return(msg.replace(CMD+"(",'').replace(")",''))

#Schedule task and format validation
def schedule(msg):
                global schedTask, logMode

                debug_report("Received request:"+msg)

                msg=msg.rstrip()
                if (msg=="TERM"):
                        cleanExit()
                elif (msg=="STATUS"):
                        publish("Alive")
                elif (msg=="LOG2SYSLOG"):
                        logMode=True
                elif (msg=="LOG_OFF"):
                        logMode=False
                elif (msg=="TIME"):
                        publish("SYSTIME:"+str(time.time()))
                        publish("SYSTIME:"+str(time.gmtime()))
                elif (msg=="SYNCTIME"):
                        publish(os_executor("ntpdate ntp.dei.uc.pt"))
                elif (msg=="RELOAD"):
                        json_parser.reload_configs(PATH,False)
                        publish("Reloaded")
                elif ("CONFIG" in msg):
                        group=param_removal("CONFIG",msg)
                        publish(json_parser.dump_configs(group))
                elif ("TESTMODE" in msg):
                        group=param_removal("TESTMODE",msg)
                        if (json_parser.group_exist(group)):
                              json_parser.test_mode(json_parser.group_cmds[group]['test_cmds'])
                        else:
                              publish("Group not found")
                elif ("NORMMODE" in msg):
                        group=param_removal("NORMMODE",msg)
                        if (json_parser.group_exist(group)):
                              json_parser.norm_mode(json_parser.group_cmds[group]['nom_cmds'])
                        else:
                              publish("Group not found")
                elif ("PUSH" in msg):
                        parsedmsg=msg.replace("PUSH(",'').replace(")",'')
                        oper_params=parsedmsg.split(';')
                        group=oper_params[0]

                        if ((len(oper_params)==2) and  (json_parser.group_exist(group))):
                              newparams=oper_params[1]
                              print(newparams)
                              if (json_parser.test_config_change(group,newparams)):
                                    publish("NEW PARAMS OK")
                                    publish(json_parser.dump_configs(group))
                              else:
                                    publish("NEW PARAMS FAILED")
                        else:
                              publish("Group not found or incorrect syntax")
                elif (':' in msg):
                        parsedmsg=msg.split(':');

                        if check_sanity(msg):
                              group=parsedmsg[0]
                              start=float(parsedmsg[1])
                              duration=float(parsedmsg[2])

                              debug_report("START EPOCH:"+str(start))
                              debug_report("START SCHEDULED FOR:"+str(time.gmtime(start)))
                              debug_report("END SCHEDULED FOR:"+str(time.gmtime(start+duration)))

                              #Old schedule cleaning and lazy zombie cleaning
                              if (group in schedTask):
                                  #print(task.is_alive())
                                  debug_report("CANCELLING OLD AND/OR ZOMBIE KILL")
                                  schedTask[group].terminate()
                                  schedTask[group].join()
                                  del schedTask[group]

                              try:
                                 schedTask[group]=multiprocessing.Process(target=pschedule,args=(start,duration,scheduler,group))
                                 schedTask[group].start()

                              except:
                                 debug_report("Cannot launch process")
                                 cleanExit()

                              #Send reply back to client
                              publish("Ok")
                        else:
                              publish("Fail")
                else:
                        debug_report("Unrecognized command")
                        publish("Unrecognized command")

def cleanExit():
	for group in schedTask:
		schedTask[group].terminate()
		schedTask[group].join()
	json_parser.reload_configs(PATH,True)
	debug_report("Terminating")
	quit()

#Log status messages
def debug_report(message):
	global logMode, DEBUG

	if ((DEBUG=="syslog") or (logMode)):
		syslog.syslog(message)
	else:
		print(message)

	#if (logMode):
	#	try:
	#		logfile.write(message+"\n") 
	#	except:
	#		logMode=False
	#		debug_report("Log file Error")

#Enable file logging
def log_on():
	global logfile,logMode
	try:
		logfile=open(PATH+"/logfile.txt","a")
		logMode=True
	except: 
		debug_report("Log file error @Logging ON")
		logMode=False

#Disables file logging
def log_off():
	global logfile,logMode

	logMode=False
	try:
		logfile.close()
	except:
		debug_report("Log file error @Logging OFF")

#Initialization
if __name__ == "__main__":

	parser=argparse.ArgumentParser()
	parser.add_argument('--daemon','-d', action='store_true', help='Start in Daemon Mode')
	#parser.add_argument('--instanceid','-id', nargs=1, action='store', dest='INSTANCE_ID', required=True, help='Instance ID (Master or specific ID)')
	args=parser.parse_args()
	#INSTANCE_ID=args.INSTANCE_ID[0]

	if (args.daemon):
		with daemon.DaemonContext():
			DEBUG="syslog"
			client=connect_mqtt()
			json_parser.starter(PATH)
			scheduler=sched.scheduler(time.time,time.sleep)    
			client.loop_forever()
	else:
		try:
			DEBUG="console"
			client=connect_mqtt()
			json_parser.starter(PATH)
			scheduler=sched.scheduler(time.time,time.sleep)    
			client.loop_forever()
		except KeyboardInterrupt:
			cleanExit()
