from helper_classes import *
import pandas as pd
import numpy as np
import random
FUNCTION_ARRIVAL = 3 
MACHINE_RESERVE = 0 
MACHINE_NOT_RESERVE = 2
SPOT_MACHINE_ARRIVAL =1  
RESERVE = 0 
DEMAND = 1
RESERVE_PROB = 0.7
SPOT_TIME_WINDOW = 1000
SPOT_MACHINE_QUANTITY_THRESHOLD = 2
AVG_VM_COMPUTE_POWER = 30


def machine_sanity_check(free_machines, busy_machines,cur_time,function_total_alive_containers):
    for vm in free_machines:
        # Removing those machines which have expired their total time
        if(vm.end_time <= cur_time):
            free_machines.remove(vm)
            
    for vm in busy_machines:
        # Removing those machines which have expired their total time
        if(vm.end_time<=cur_time ):
            busy_machines.remove(vm)
            function_total_alive_containers[vm.last_hash_fun] = function_total_alive_containers.get(vm.last_hash_fun,0) - 1
            continue 
        # Adding machines that have finished their work to the free machines list
        if(vm.available_time <= cur_time):
            busy_machines.remove(vm)
            function_total_alive_containers[vm.last_hash_fun] = function_total_alive_containers.get(vm.last_hash_fun,0) - 1
            free_machines.append(vm)
            
            
def get_new_vm(R_D_S_Stats,func_node,type,cur_time,arr_time,curr_task,vm_data):
    
    # Returns least memory vm that has enough memory for this task 
    
    for key,vm in vm_data.items():
        if(vm.memory >= func_node.memory):
            new_vm = machine(key, vm.compute_power,vm.CPU,vm.memory,vm.reserve_cost,vm.ondemand_cost,0,None,None,None,0)
            if(type==RESERVE):
                #    print(f"RESERVE : {vm.reserve_cost}  {new_vm}")
                R_D_S_Stats.reserve_cost += vm.reserve_cost
            else :
                #    print(f"DEMAND  : {vm.ondemand_cost}  {new_vm}")
                R_D_S_Stats.ondemand_cost += vm.ondemand_cost
                
            new_vm.end_time = cur_time + 3600
                
            return new_vm
    
    return None 


def update_machine(new_vm , task,cur_time,time_on_this_vm):
    new_vm.available_time = cur_time + time_on_this_vm  
    new_vm.last_hash_fun = task.hashfunction
    new_vm.running_function_id = task.id
    new_vm.running_worfklow_id = task.workflowid
    
    
def add_children_to_queue(cur_node , cur_heap , global_finish_time,false_addition,taskMap):
    for node in cur_node.children:
        max_finish_time = global_finish_time[cur_node.id]    
        for par in taskMap[int(node)].parentids:
            time_val = global_finish_time.get(par,-1)
            if(time_val==-1):
                max_finish_time = -1 
                break 
        
            max_finish_time = max(max_finish_time, time_val)
        if(max_finish_time == -1):
            continue
        # false_addition[node]=False
        cur_heap.add_to_queue(event(max_finish_time,FUNCTION_ARRIVAL,node))




def choose_vm(free_machines,cur_node,mem_list,function_total_alive_containers,arr_time,taskMap):
    
    suitable_vms = []
    for ind in range(0,len(free_machines)):
        vm = free_machines[ind]
        time_on_this_vm = cur_node.execution_time / vm.compute_power
        if(vm.last_hash_fun != cur_node.hashfunction):
            time_on_this_vm += cur_node.cold_start_time / vm.compute_power
        if(vm.memory >= cur_node.memory and vm.end_time > (arr_time + time_on_this_vm) ):
            suitable_vms.append(ind)
    
    if(len(suitable_vms)==0):
        return None
    chosen_vm_ind = random.choice(suitable_vms) 
    
    return chosen_vm_ind


def get_bid_price(reward_time_concentration, curtime , vm_type, ondemand_price,cur_spot_price,alpha =0.02):
    
    score = reward_time_concentration.get(vm_type,CumulativeScore()).query(curtime , curtime+3600)
    bid = ondemand_price - (ondemand_price-cur_spot_price)*np.exp(-alpha*score)
    # print(f"{cur_spot_price} , {bid} , {ondemand_price} " )
    return bid 
    
    



def RDS_Random(taskMap,workflowMap,vm_data,avg_compute_pow=40,res_prb=0.7):
    global relative_function_deadline
    global RESERVE_PROB
    global AVG_VM_COMPUTE_POWER
    AVG_VM_COMPUTE_POWER = avg_compute_pow
    RESERVE_PROB = res_prb

    overall_events = event_heap() 

    incoming_tasks = event_heap()

    function_deadline={}

    for workflow in list(workflowMap.values()):

        # print(workflow)
        # print(f"Actual Arrival Time : {workflow.arrival_time} , Predicted : { workflow.predicted_arrival_time}")
        for node in workflow.start_nodes:
            node = int(node)
            overall_events.add_to_queue(event(workflow.arrival_time,FUNCTION_ARRIVAL, node))
            incoming_tasks.add_to_queue(event(workflow.predicted_arrival_time, FUNCTION_ARRIVAL,node))
        
        for node_id in workflow.nodes:
            function_deadline[node_id]=workflow.arrival_time+workflow.deadline

    df = pd.read_csv('../Dataset/spotprices.csv')

    for index, row in df.iterrows():
        if(row['price'] >= vm_data[row['instance_type']].ondemand_cost):
            continue 
        overall_events.add_to_queue(event(row['time'],SPOT_MACHINE_ARRIVAL, (row['instance_type'] , row['price'])))
    


    free_machines= []
    busy_machines= []
    global_finish_time = {}
    vm_schedule= []
    R_D_S_Stats = wf_run_stats()
    reserve_vms = []
    function_total_alive_containers = {}
    false_addition = {}
    reward_time_concentration= {}

    # key is machine instance type and val is list of timepoints for that instance type 
    machines_not_reserved = {}

    mem_list = []
    for vm in vm_data.values():
        mem_list.append(vm.memory)


    while(not incoming_tasks.isempty()):
        cur_top_element = incoming_tasks.pop_from_queue()
        cur_node_id = cur_top_element.item
        cur_time = cur_top_element.time
        cur_node = taskMap[cur_node_id]
        # print(cur_node)
        # Removes Expired machines and updates status of machines
        machine_sanity_check(free_machines,busy_machines,cur_time,function_total_alive_containers)
        
        time_on_this_vm = 0

        best_vm_index = choose_vm(free_machines,cur_node,mem_list,function_total_alive_containers,cur_time,taskMap)

        if(best_vm_index==None):
            
            new_vm = get_new_vm(R_D_S_Stats,cur_node,RESERVE,cur_time,cur_time,cur_node,vm_data)
            if new_vm == None:
                continue
            time_on_this_vm = cur_node.execution_time/new_vm.compute_power+cur_node.cold_start_time/new_vm.compute_power
            update_machine(new_vm,cur_node,cur_time,time_on_this_vm)
            vm_schedule.append(new_vm)
            busy_machines.append(new_vm)
            if(new_vm.type not in reward_time_concentration):
                reward_time_concentration[new_vm.type] = CumulativeScore()
            reward_time_concentration[new_vm.type].add_pair(cur_time,cur_node.reward)
            if(random.random() < RESERVE_PROB): 
            #     # print("ASD")
                overall_events.add_to_queue(event(cur_time,MACHINE_RESERVE, new_vm))
            else:
                # for machine in all_spot_machines :
                R_D_S_Stats.reserve_cost -= new_vm.reserve_cost
                # overall_events.add_to_queue(event(cur_time, MACHINE_NOT_RESERVE ,new_vm))
                if(new_vm.type not in machines_not_reserved):
                    machines_not_reserved[new_vm.type]=[]
                machines_not_reserved[new_vm.type].append(cur_time)
            
        else:

            chosen_vm_ind = best_vm_index 
            my_vm = free_machines[chosen_vm_ind]

            free_machines.pop(chosen_vm_ind) 

            time_on_this_vm = cur_node.execution_time/my_vm.compute_power
            if(my_vm.last_hash_fun != cur_node.hashfunction):
                time_on_this_vm += cur_node.cold_start_time/my_vm.compute_power
            
            update_machine(my_vm,cur_node,cur_time,time_on_this_vm)
            busy_machines.append(my_vm)
        
        function_total_alive_containers[cur_node.hashfunction] = function_total_alive_containers.get(cur_node.hashfunction,0) + 1
        
        global_finish_time[cur_node_id] = cur_time + time_on_this_vm
        add_children_to_queue(cur_node,incoming_tasks,global_finish_time,false_addition,taskMap)

    global_finish_time = {}
    function_ran = 0
    machine_count = {}
    free_machines = []
    busy_machines = []
    vm_schedule = []
    spot_machines = {}
    function_total_alive_containers = {}
    spot_machines_by_vm_type = {}
    total_busy_revokes = 0 
    total_free_revokes = 0 
    # R_D_S_Stats

    # instance type - >  list of VMs ( spot price bid , task arrival time , tasknode )
    # new spot instance arrives : 
    # 1. check for this instance's currently running VMs  
    # pay spot price
    # i1 (100 , m_id)
    # i1 120 
    while(not overall_events.isempty()):

        cur_top_element = overall_events.pop_from_queue()
        cur_time = cur_top_element.time
        
        if(cur_top_element.type == MACHINE_RESERVE):
            new_vm = cur_top_element.item
            new_vm.end_time = cur_time + 3600 
            new_vm.available_time = cur_time  
            
            free_machines.append(new_vm)
            # print(f"RESERVE : {cur_time}  {new_vm.type} {new_vm.reserve_cost}")
            continue
        elif(cur_top_element.type==SPOT_MACHINE_ARRIVAL):
            # continue 
            type_price_tup = cur_top_element.item 
            cur_type = type_price_tup[0]
            valid_times =[]
            spot_counter = 0 
            
            
            new_spot_tuple = []
            for spot_tup in spot_machines_by_vm_type.get(cur_type,[]):
                if cur_time - spot_tup[1] < 3600:
                    if type_price_tup[1] <= spot_tup[2]:
                        new_spot_tuple.append(spot_tup) 
                    else:
                        # print("REVOKED")
                        # total_revokes+=1
                        for vm in free_machines:
                            if vm.id == spot_tup[0]:
                                R_D_S_Stats.total_spot_cost-= spot_tup[2]*( 3600 - cur_time + spot_tup[1])/3600 
                                free_machines.remove(vm)
                                total_free_revokes+=1
                        
                        for vm in busy_machines:
                            if vm.id == spot_tup[0]:
                                busy_machines.remove(vm)
                                total_busy_revokes+=1
                                global_finish_time[vm.running_function_id] = -1 
                                function_total_alive_containers[vm.last_hash_fun] = function_total_alive_containers.get(vm.last_hash_fun,0) - 1
                                overall_events.add_to_queue(event(cur_time,FUNCTION_ARRIVAL,vm.running_function_id))
                                R_D_S_Stats.total_spot_cost-= spot_tup[2]*( 3600 - cur_time + spot_tup[1])/3600
                                # for child in taskMap[vm.running_function_id].children:
                                #     false_addition[child]=True

            spot_machines_by_vm_type[cur_type] = new_spot_tuple

            if( cur_type not in machines_not_reserved):
                continue 
            for time_points in machines_not_reserved[cur_type]:
                if(abs(time_points - cur_time) < SPOT_TIME_WINDOW and spot_counter<SPOT_MACHINE_QUANTITY_THRESHOLD):
                    new_vm = machine(cur_type, vm_data[cur_type].compute_power,vm_data[cur_type].CPU,vm_data[cur_type].memory,vm_data[cur_type].reserve_cost,vm_data[cur_type].ondemand_cost,0,None,None,None,0)
                    new_vm.end_time = cur_time + 3600 
                    new_vm.available_time = cur_time  
                    free_machines.append(new_vm)
                    cur_bid = get_bid_price(reward_time_concentration,cur_time,cur_type,vm_data[cur_type].ondemand_cost,type_price_tup[1])
                    R_D_S_Stats.total_spot_cost+= cur_bid
                    
                    # print(f"SPOT : {cur_time}  {new_vm.type} {type_price_tup[1]}")
                    if cur_type not in spot_machines_by_vm_type:
                        spot_machines_by_vm_type[cur_type]=[]
                    spot_machines_by_vm_type[cur_type].append((new_vm.id,cur_time,cur_bid))
                    spot_counter+=1
                else :
                    valid_times.append(time_points)    
            
            machines_not_reserved[cur_type] = valid_times
            continue 
        
        # Normal Case
        
        # Check if any parent was revoked 
        cur_node_id = cur_top_element.item
        break_flag = False
        for par in taskMap[int(cur_node_id)].parentids:
            time_val = global_finish_time.get(par,-1)
            if(time_val==-1):
                break_flag = True
                break 
        if(break_flag):
            continue 
        cur_node = taskMap[cur_node_id]
        machine_sanity_check(free_machines,busy_machines,cur_time,function_total_alive_containers)
        best_vm_index = choose_vm(free_machines,cur_node,mem_list,function_total_alive_containers,cur_time,taskMap)
        
        time_on_this_vm = 0
        if(best_vm_index ==None):
            new_vm = get_new_vm(R_D_S_Stats,cur_node,DEMAND,cur_time,cur_time,cur_node,vm_data)
            # print(f"DEMAND : {cur_time}  {new_vm.type} {new_vm.ondemand_cost}")
            if new_vm == None:
                continue
            to_be_rem = -1
            if( new_vm.type in machines_not_reserved):
            
            
                for time_point in machines_not_reserved[new_vm.type]:
                    if(abs(time_point - cur_time) < SPOT_TIME_WINDOW ):
                        to_be_rem = time_point
                        break
                if(to_be_rem != -1):
                    machines_not_reserved[new_vm.type].remove(to_be_rem)
                    
            time_on_this_vm = cur_node.execution_time/new_vm.compute_power + cur_node.cold_start_time/new_vm.compute_power
            update_machine(new_vm,cur_node,cur_time,time_on_this_vm)
            busy_machines.append(new_vm)
            
        else:

            chosen_vm_ind = best_vm_index
            my_vm = free_machines[chosen_vm_ind]

            free_machines.pop(chosen_vm_ind) 
            time_on_this_vm = cur_node.execution_time / my_vm.compute_power
            if(my_vm.last_hash_fun != cur_node.hashfunction):
                time_on_this_vm += cur_node.cold_start_time/ my_vm.compute_power
            update_machine(my_vm,cur_node,cur_time,time_on_this_vm)
            busy_machines.append(my_vm)
        
        global_finish_time[cur_node_id] = cur_time + time_on_this_vm
        add_children_to_queue(cur_node,overall_events,global_finish_time,false_addition,taskMap)

    total_reward=0
    total_deadlines_missed =0

    total_count={}
    deadline_miss={}

    for workflow in list(workflowMap.values()):
        max_finish_time=-1
        for node_id in workflow.nodes:
            if global_finish_time.get(int(node_id),-1)==-1:
                max_finish_time=-1
                break
            max_finish_time=max(max_finish_time,global_finish_time[int(node_id)])
        
        if max_finish_time==-1:
            total_deadlines_missed+=1
            print(workflow.reward)
            print(max_finish_time)
            continue
        if max_finish_time <= workflow.arrival_time+workflow.deadline:
        
            R_D_S_Stats.total_reward+=workflow.reward
        else :
            total_deadlines_missed+=1
 
    total_cost=R_D_S_Stats.total_spot_cost + R_D_S_Stats.reserve_cost + R_D_S_Stats.ondemand_cost

    return "R+D+S_Random",str(R_D_S_Stats.reserve_cost),str(R_D_S_Stats.ondemand_cost),str(R_D_S_Stats.total_spot_cost),str(total_cost),str(R_D_S_Stats.total_reward),str(R_D_S_Stats.total_reward-total_cost),total_deadlines_missed
