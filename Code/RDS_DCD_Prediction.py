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
SPOT_MACHINE_QUANTITY_THRESHOLD = 10
AVG_VM_COMPUTE_POWER = 25
WINDOW_LENGTH = 500
# TOTAL_COLD_START_PENALTY = 0
PSI1 = 1 
PSI2 = 30 
PSI3 = 100
def get_spot_data(filename,vm_data):
    df = pd.read_csv("../Dataset/Spot_Pred.csv")
    spot_machine_concentration = {}
    for index, row in df.iterrows():
        if(row['modified_ewma'] <= vm_data[row['instance_type']].reserve_cost):
            if(row['instance_type'] not in spot_machine_concentration):
                spot_machine_concentration[row['instance_type']] = CumulativeScore()
            spot_machine_concentration[row['instance_type']].add_pair(row['time'], 1)
            # overall_events.add_to_queue(event(row['time'],SPOT_MACHINE_ARRIVAL, (row['instance_type'] , row['price'])))
    
    return spot_machine_concentration

def machine_sanity_check(free_machines, busy_machines,cur_time,function_total_alive_containers):
    for vm in free_machines:
        # Removing those machines which have expired their total time
        if(vm.end_time <= cur_time):
            free_machines.remove(vm)
            
    for vm in busy_machines:
        # Removing those machines which have expired their total time
        
        # Adding machines that have finished their work to the free machines list
        if(vm.available_time <= cur_time):
            busy_machines.remove(vm)
            function_total_alive_containers[vm.last_hash_fun] = function_total_alive_containers.get(vm.last_hash_fun,0) - 1
            free_machines.append(vm)
            continue
        
        # if(vm.end_time<=cur_time ):
        #     busy_machines.remove(vm)
        #     function_total_alive_containers[vm.last_hash_fun] = function_total_alive_containers.get(vm.last_hash_fun,0) - 1
        #     continue 
            
            
def get_new_vm(R_D_S_Stats,func_node,type,cur_time,arr_time,curr_task,vm_data):
    
    # Returns least memory vm that has enough memory for this task 
    
    for key,vm in vm_data.items():
        if(vm.memory >= func_node.memory):
            new_vm = machine(key, vm.compute_power,vm.CPU,vm.memory,vm.reserve_cost,vm.ondemand_cost,0,None,None,None,0)
            if arr_time+curr_task.execution_time/(vm.compute_power) + curr_task.cold_start_time/(vm.compute_power) <= relative_function_deadline[curr_task.id]:
                if(type==RESERVE):
                    #    print(f"RESERVE : {vm.reserve_cost}  {new_vm}")
                    R_D_S_Stats.reserve_cost += vm.reserve_cost
                else :
                    #    print(f"DEMAND  : {vm.ondemand_cost}  {new_vm}")
                    R_D_S_Stats.ondemand_cost += vm.ondemand_cost
                
                new_vm.end_time = cur_time + 3600
                
                return new_vm
    
    # print("NO VM FOUND")
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


def get_priority(vm,cur_time,function_total_alive_containers,taskMap):
    if taskMap.get(vm.running_function_id,0) ==0 : 
        return (-cur_time +vm.available_time)*PSI1 + 300*PSI2*(vm.memory/256.0)+ 900*PSI3*((1.4+0.3*function_total_alive_containers.get(vm.last_hash_fun,0))* 1)/(vm.compute_power)
    
    # print(PSI1, PSI2,PSI3)
    # print((-cur_time +vm.available_time)*PSI1 , PSI2*300*(vm.memory/256.0) ,function_total_alive_containers.get(vm.last_hash_fun,0))
    return (-cur_time +vm.available_time)*PSI1 + 300*PSI2*(vm.memory/256.0)+ 900*PSI3*((1.4+0.3*function_total_alive_containers.get(vm.last_hash_fun,0))* taskMap.get(vm.running_function_id,0).cold_start_time)/(vm.compute_power)


def choose_vm(free_machines,curr_task,mem_list,function_total_alive_containers,arr_time,taskMap):
    
    best_mem=[]
    for mem in mem_list:
        if mem>=curr_task.memory:
            best_mem.append(mem)
    coldstart_saving_machines=[]
    available_machines=[]
    for i in range(len(free_machines)):
        vm=free_machines[i]
        if vm.memory>=curr_task.memory:
            if vm.last_hash_fun==curr_task.hashfunction:
                if arr_time+curr_task.execution_time/(vm.compute_power)<=vm.end_time and arr_time+curr_task.execution_time/(vm.compute_power) <= relative_function_deadline[curr_task.id]:
                    coldstart_saving_machines.append(i)
            else:
                if arr_time+curr_task.execution_time/(vm.compute_power) + curr_task.cold_start_time/vm.compute_power<=vm.end_time and arr_time+curr_task.execution_time/(vm.compute_power) + curr_task.cold_start_time/vm.compute_power <= relative_function_deadline[curr_task.id]:
                    available_machines.append(i)
    
    chosen_machine_ind = None
    if len(coldstart_saving_machines)==0:
        best_vm_index = None
        best_vm_priority = 1e18
        for ind in available_machines:
            cur_vm_priority = get_priority(free_machines[ind],arr_time,function_total_alive_containers,taskMap)
            if(cur_vm_priority < best_vm_priority):
                best_vm_index = ind
                best_vm_priority = cur_vm_priority
        chosen_machine_ind = best_vm_index
    else:    
        for mem in best_mem:
            best_available_machine=[ind for ind in coldstart_saving_machines if mem==free_machines[ind].memory]
            if len(best_available_machine)==0: 
                continue
            best_vm_index = None
            best_vm_priority = -2
            for ind in best_available_machine:
                cur_vm_priority= free_machines[ind].available_time
                if(cur_vm_priority > best_vm_priority):
                    best_vm_index = ind 
                    best_vm_priority = cur_vm_priority
            chosen_machine_ind = best_vm_index
            break
    if chosen_machine_ind == None:
        return None
    
    return chosen_machine_ind


def get_bid_price(reward_time_concentration, curtime , vm_type, ondemand_price,cur_spot_price,alpha =0.02):
    
    score = reward_time_concentration.get(vm_type,CumulativeScore()).query(curtime , curtime+3600)
    bid = ondemand_price - (ondemand_price-cur_spot_price)*np.exp(-alpha*score)
    # print(f"{cur_spot_price} , {bid} , {ondemand_price} " )
    return bid 
    
    

from collections import defaultdict, deque
# Initialize deadlines dictionary
relative_function_deadline = {}
def compute_task_deadlines(nodes, edges, exec_times, cold_start_times, workflow_arrival_time, workflow_deadline):
    graph = defaultdict(list)
    indegree = {node: 0 for node in nodes}
    for u, v, _ in edges:
        graph[u].append(v)
        indegree[v] += 1

    # Step 1: Assign depths using BFS
    depth = {}
    queue = deque([node for node in nodes if indegree[node] == 0])
    for node in queue:
        depth[node] = 0

    while queue:
        node = queue.popleft()
        for neighbor in graph[node]:
            if neighbor not in depth or depth[neighbor] < depth[node] + 1:
                depth[neighbor] = depth[node] + 1
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    # Step 2: Collect nodes by depth
    depth_nodes = defaultdict(list)
    for node, d in depth.items():
        depth_nodes[d].append(node)

    # Step 3: Calculate max exec_time per depth (no cold start)
    depth_execs = {}
    for d, nodes_at_depth in depth_nodes.items():
        depth_execs[d] = max((exec_times[n] + cold_start_times[n])  for n in nodes_at_depth)

    # Step 4: Divide the deadline proportionally
    total_weight = sum(depth_execs.values())
    depth_deadlines = {}
    elapsed_time = workflow_arrival_time
    for d in sorted(depth_execs):
        share = (workflow_deadline - workflow_arrival_time) * (depth_execs[d] / total_weight)
        elapsed_time += share
        depth_deadlines[d] = elapsed_time

    # Step 5: Assign deadline to each node based on depth
    # relative_function_deadline = {}
    for node in nodes:
        # print(f"Node {node} - Depth: {depth[node]}, Deadline: {depth_deadlines[depth[node]]}, Exec Time: {exec_times[node]}")
        
        relative_function_deadline[node] = depth_deadlines[depth[node]]



def RDS_DCD_Prediction(psi1 , psi2, psi3, taskMap,workflowMap,vm_data,avg_compute_pow=40,res_prb=0.7):
    global relative_function_deadline
    global RESERVE_PROB
    global AVG_VM_COMPUTE_POWER
    global PSI1
    global PSI2
    global PSI3
    AVG_VM_COMPUTE_POWER = avg_compute_pow
    RESERVE_PROB = res_prb
    # if(which_psi == 1):
        
    PSI1 = psi1 
    PSI2 = psi2
    PSI3 = psi3
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

    relative_function_deadline.clear()
    for workflow in list(workflowMap.values()):
        compute_task_deadlines(workflow.nodes, workflow.edges, {node: taskMap[node].execution_time for node in workflow.nodes}, {node: taskMap[node].cold_start_time for node in workflow.nodes}, workflow.arrival_time, workflow.arrival_time+workflow.deadline)
    
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
    spot_machine_concentration = get_spot_data("Spot_Pred.csv",vm_data)
    reserve_not_taken_concentration = {}
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
            should_reserve = False 
            check_range_lower = cur_time - WINDOW_LENGTH
            check_range_upper = cur_time + WINDOW_LENGTH 
            if(new_vm.type not in  reserve_not_taken_concentration):
                reserve_not_taken_concentration[new_vm.type] = CumulativeScore()
            
            if(new_vm.type not in spot_machine_concentration):
                should_reserve = True   
            elif(spot_machine_concentration[new_vm.type].query(check_range_lower,check_range_upper) - reserve_not_taken_concentration[new_vm.type].query(check_range_lower,check_range_upper) >=1):
                should_reserve = False
            else :
                should_reserve = True
            # reserve_not_taken_concentration
            R_D_S_Stats.total_reserve_opportunities+=1
            if(should_reserve): 
            #     # print("ASD")
                R_D_S_Stats.total_reserves+=1
                overall_events.add_to_queue(event(cur_time,MACHINE_RESERVE, new_vm))
            else:
                # for machine in all_spot_machines :
                reserve_not_taken_concentration[new_vm.type].add_pair(cur_time , 1)
                if(new_vm.type not in reward_time_concentration):
                    reward_time_concentration[new_vm.type] = CumulativeScore()
                reward_time_concentration[new_vm.type].add_pair(cur_time,cur_node.reward)
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
    function_total_alive_containers.clear()
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
            R_D_S_Stats.total_cold_start_count+=1
            R_D_S_Stats.total_cold_start_time += cur_node.cold_start_time/new_vm.compute_power
            time_on_this_vm = cur_node.execution_time/new_vm.compute_power + cur_node.cold_start_time/new_vm.compute_power
            update_machine(new_vm,cur_node,cur_time,time_on_this_vm)
            busy_machines.append(new_vm)
            
        else:

            chosen_vm_ind = best_vm_index
            my_vm = free_machines[chosen_vm_ind]

            free_machines.pop(chosen_vm_ind) 
            time_on_this_vm = cur_node.execution_time / my_vm.compute_power
            if(my_vm.last_hash_fun != cur_node.hashfunction):
                R_D_S_Stats.total_cold_start_count+=1
                R_D_S_Stats.total_cold_start_time += cur_node.cold_start_time/new_vm.compute_power
                time_on_this_vm += cur_node.cold_start_time/ my_vm.compute_power
            update_machine(my_vm,cur_node,cur_time,time_on_this_vm)
            busy_machines.append(my_vm)
        
        function_total_alive_containers[cur_node.hashfunction] = function_total_alive_containers.get(cur_node.hashfunction,0) + 1
        global_finish_time[cur_node_id] = cur_time + time_on_this_vm
        add_children_to_queue(cur_node,overall_events,global_finish_time,false_addition,taskMap)

    total_reward=0
    total_deadlines_missed =0

    total_count={}
    deadline_miss={}
    mindiff=1e9
    for workflow in list(workflowMap.values()):
        max_finish_time=-1
        for node_id in workflow.nodes:
            if global_finish_time.get(int(node_id),-1)==-1:
                max_finish_time=-1
                break
            max_finish_time=max(max_finish_time,global_finish_time[int(node_id)])
        
        if max_finish_time==-1:
            total_deadlines_missed+=1
            # print(workflow.reward)
            # print(max_finish_time)
            continue
        if max_finish_time <= workflow.arrival_time+workflow.deadline:
            mindiff=min(workflow.arrival_time+workflow.deadline-max_finish_time,mindiff)
            R_D_S_Stats.total_reward+=workflow.reward
        else :
            total_deadlines_missed+=1
 
    total_cost=R_D_S_Stats.total_spot_cost + R_D_S_Stats.reserve_cost + R_D_S_Stats.ondemand_cost
    
    # print(f"bidding busy revokes {total_busy_revokes}")
    # print(f"bidding free revokes {total_free_revokes}")
    # print(f"bidding min diff {mindiff}")
    
    # print(F"Total Reserve Opportunities {R_D_S_Stats.total_reserve_opportunities}")
    # print(F"Total Actual Reserves {R_D_S_Stats.total_reserves}")
    # print(f"Total_Cold_Start_Time {R_D_S_Stats.total_cold_start_time}, Total_Cold_Start_Count : {R_D_S_Stats.total_cold_start_count}\n")
    return "R+D+S_DCD_Prediction",str(R_D_S_Stats.reserve_cost),str(R_D_S_Stats.ondemand_cost),str(R_D_S_Stats.total_spot_cost),str(total_cost),str(R_D_S_Stats.total_reward),str(R_D_S_Stats.total_reward-total_cost),str(R_D_S_Stats.total_cold_start_time),str(R_D_S_Stats.total_cold_start_count),total_deadlines_missed
