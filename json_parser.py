
import json
import shlex
import subprocess

#Base template
profile=["tc class %cmd dev eth0 parent 1:1 classid 1:%flowid htb rate %bw_dl ceil %bw_dl burst 1500 prio 0 cburst 1500 quantum 1500",
"tc class %cmd dev eth1 parent 1:1 classid 1:%flowid htb rate %bw_ul ceil %bw_ul burst 1500 prio 0 cburst 1500 quantum 1500",
"tc qdisc %cmd dev eth0 parent 1:%flowid handle %handleid: netem delay %latency_dl loss %loss_dl limit 32",
"tc qdisc %cmd dev eth1 parent 1:%flowid handle %handleid: netem delay %latency_ul loss %loss_ul limit 32",
"tc filter %cmd dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst %ip_left/32 match ip src %ip_right/32 flowid 1:%flowid",
"tc filter %cmd dev eth1 protocol ip parent 1:0 prio 1 u32 match ip src %ip_left/32 match ip dst %ip_right/32 flowid 1:%flowid"]

#generate command set from configs
def gen_cmd_set(profile,config,ip_pairs,mode,flowid_base,handleid_base):
	attributes=["bw","loss","latency"]
	direction=["ul","dl"] #UP=0, DOWN=1

	try:
		#Replace bw and netem parameters
		profile_init=[entry.replace('%cmd',mode,1 ) for entry in profile]
		for dir in [0,1]:
			for attr in attributes:
				profile_init=[entry.replace('%'+attr+'_'+direction[dir],config[dir][attr] ,2 ) for entry in profile_init]
	
		#Create flowids and expand profile for IP pairs
		profile_init_all=[]
		flowid=flowid_base
		handleid=handleid_base
		pair=["ip_left","ip_right"]	
		for pair_entry in ip_pairs:
			profile_ip_pair=profile_init
			profile_ip_pair=[entry.replace('%flowid',str(flowid),1) for entry in profile_ip_pair]
			profile_ip_pair=[entry.replace('%handleid',str(handleid),1) for entry in profile_ip_pair]
			for ip_side in pair:
				profile_ip_pair=[entry.replace('%'+ip_side,pair_entry[ip_side],1) for entry in profile_ip_pair]
			flowid=flowid+1
			handleid=handleid+1

			#lexical parsing for proper invocation of subprocess spawn
			profile_ip_pair=[shlex.split(entry) for entry in profile_ip_pair]
			profile_init_all.append(profile_ip_pair)		
	except KeyError:
		print("JSON Key Error")
		quit()

	return(profile_init_all)		
		

#lexical expansion
def shlexCMDExec(cmd):
	process=subprocess.run(cmd,stdout=subprocess.PIPE,universal_newlines=True)
	return 0

#bridge_start
def start_bridge():
	process=subprocess.run([PATH+"/"+"netem_MQTT_init.sh","clear","bridge0"],stdout=subprocess.PIPE,universal_newlines=True)
	process=subprocess.run([PATH+"/"+"netem_MQTT_init.sh","apply","bridge0"],stdout=subprocess.PIPE,universal_newlines=True)

#execute script to create bridge and TC root
#execute configuration rules + add policies
#
def init_mode(init_cmd_set):
	[[shlexCMDExec(cmd) for cmd in entry] for entry in init_cmd_set]

			
#run config rules and change policies
def test_mode(test_cmd_set):
	[[shlexCMDExec(cmd) for cmd in entry[:-2] ] for entry in test_cmd_set]
	#B=[list(map(shlexCMDExec,entry[:-2])) for entry in test_cmd_set]

#run config rules and reinstate original policies
def norm_mode(nom_cmd_set):
	[[shlexCMDExec(cmd) for cmd in entry[:-2] ] for entry in nom_cmd_set]
	#B=[list(map(shlexCMDExec,entry[:-2])) for entry in nom_cmd_set]

#Load base JSON
def config_read(PATH):
	group_config=dict()
	# Opening JSON file
	try:
		f = open(PATH+"/"+'setup.json',)
	except (FileNotFoundError,IOError):
		print("Cannot open "+PATH+"/"+'setup.json')
		quit()

	# returns JSON object as 
	# a dictionary
	try:
		data = json.load(f)
		try:	
			groups=data['groups']
			for group in groups:
				ID=group['id']
				group_config[ID]={}
				group_config[ID]['ip_pairs']=group['address_pairs']
				group_config[ID]['nom_config']=group['configUP_nom']
				group_config[ID]['nom_config'].append(group['configDOWN_nom'][0])
				group_config[ID]['test_config']=group['configUP_test']
				group_config[ID]['test_config'].append(group['configDOWN_test'][0])

		except KeyError:
			f.close()
			print("JSON Key Error")
			quit()  
	# Closing file
		f.close()
	except json.JSONDecodeError as err:
		print("JSON Decoding Error")
		print(err.msg)
		quit()

	return group_config

def starter(path):
	global group_cmds,  group_configs
	global PATH

	PATH=path
	group_configs=config_read(PATH)

	flowid_base=10
	handleid_base=21

	group_cmds=dict()
	for group in group_configs:
		group_cfg=group_configs[group]		
		group_cmds[group]={}
		group_cmds[group]["flowid_base"]=flowid_base
		group_cmds[group]["handleid_base"]=handleid_base
		group_cmds[group]['init_cmds']=gen_cmd_set(profile,group_cfg['nom_config'],group_cfg['ip_pairs'],"add",flowid_base,handleid_base)
		group_cmds[group]['nom_cmds']=gen_cmd_set(profile,group_cfg['nom_config'],group_cfg['ip_pairs'],"change",flowid_base,handleid_base)
		group_cmds[group]['test_cmds']=gen_cmd_set(profile,group_cfg['test_config'],group_cfg['ip_pairs'],"change",flowid_base,handleid_base)
		flowid_base+=len(group_cfg['ip_pairs'])
		handleid_base+=len(group_cfg['ip_pairs'])

	start_bridge()
	for group in group_cmds:
		init_mode(group_cmds[group]['init_cmds'])

#reloads config from file
#reset_norm defines if normal mode configs are to be reapplied
def reload_configs(path,reset_norm):
	global group_cmds,  group_configs
	global PATH

	PATH=path
	group_configs=config_read(PATH)

	flowid_base=10
	handleid_base=21

	group_cmds=dict()
	for group in group_configs:
		group_cfg=group_configs[group]		
		group_cmds[group]={}
		group_cmds[group]["flowid_base"]=flowid_base
		group_cmds[group]["handleid_base"]=handleid_base
		group_cmds[group]['init_cmds']=gen_cmd_set(profile,group_cfg['nom_config'],group_cfg['ip_pairs'],"add",flowid_base,handleid_base)
		group_cmds[group]['nom_cmds']=gen_cmd_set(profile,group_cfg['nom_config'],group_cfg['ip_pairs'],"change",flowid_base,handleid_base)
		group_cmds[group]['test_cmds']=gen_cmd_set(profile,group_cfg['test_config'],group_cfg['ip_pairs'],"change",flowid_base,handleid_base)
		flowid_base+=len(group_cfg['ip_pairs'])
		handleid_base+=len(group_cfg['ip_pairs'])

	if (reset_norm):
		for group in group_cmds:
			norm_mode(group_cmds[group]['nom_cmds'])

#loads test config from params
#designed for online param update
def test_config_change(group,params):
	global group_cmds, group_configs

	#test_cmds, test_config, ip_pairs
	if (not(group_exist(group))):
		print("Group does not exist")
		return False

	# returns JSON object as 
	# a dictionary
	try:
		data = json.loads(params)

		try:
			test_config=data['configUP_test']
			test_config.append(data['configDOWN_test'][0])

			flowid_base=group_cmds[group]["flowid_base"]
			handleid_base=group_cmds[group]["handleid_base"]

			test_cmds=gen_cmd_set(profile,test_config,group_configs[group]['ip_pairs'],"change",flowid_base,handleid_base)
			group_cmds[group]['test_cmds']=test_cmds

			group_configs[group]['test_config']=test_config

		except KeyError:
			print("JSON Key error")
			return False

	except json.JSONDecodeError as err:
		print("JSON Decoding Error in Runtime Test Param Change")
		print(err.msg)
		return False

	return True

def group_exist(group):
	return (group in group_cmds)

def dump_configs(group):
	if (group_exist(group)):
		out=""
		out="NOMINAL UP"+str(group_configs[group]['nom_config'][0])+"\n"
		out=out+"NOMINAL DOWN"+str(group_configs[group]['nom_config'][1])+"\n"
		out=out+"TEST UP"+str(group_configs[group]['test_config'][0])+"\n"
		out=out+"TEST DOWN"+str(group_configs[group]['test_config'][1])+"\n"
	else:
		out="Group not found"
	return out

if __name__ == "__main__":
	starter()
