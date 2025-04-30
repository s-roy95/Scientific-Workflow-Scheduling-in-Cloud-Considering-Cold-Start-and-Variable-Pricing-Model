from helper_classes import *
import pandas as pd
import numpy as np
import math

NUM_OF_TASK_CLASSES=5
NUM_OF_MACHINES_CLASSES=5
FUNCTION_ARRIVAL = 4
TASK_SCHEDULING = 5
SPOT_MACHINE_ARRIVAL = 2
MACHINE_FREEDOM = 0
MACHINE_PROVISION = 3
MACHINE_END_TIME = 1
AVG_VM_COMPUTE_POWER = 40
TASK_SCHEDULING_INTERVAL = 5
SPOT_THRESHOLD = 5
MACHINE_PROVISION_INTERVAL= 4
END_TIME = 1.3*86400
QUEUE_TASK_COUNTER=0
DEMAND_CONTR=1

def compute_class(node, current_time):
    slack_time = relative_function_deadline[node.id] - node.execution_time/AVG_VM_COMPUTE_POWER -node.cold_start_time/AVG_VM_COMPUTE_POWER - current_time
    
    penalty = node.execution_time/AVG_VM_COMPUTE_POWER + node.cold_start_time/AVG_VM_COMPUTE_POWER + TASK_SCHEDULING_INTERVAL+MACHINE_PROVISION_INTERVAL
    # print(math.ceil(slack_time/(penalty*50*DEMAND_CONTR))-1)
    # if slack_time <= 0:
    #     print(slack_time)
    return min(math.ceil(slack_time/(50*penalty*DEMAND_CONTR))-1,NUM_OF_TASK_CLASSES-1), slack_time
    # return 0, slack_time    
    
def add_children_to_queue(cur_node , cur_heap , global_finish_time,taskMap):
    global QUEUE_TASK_COUNTER
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
        QUEUE_TASK_COUNTER+=1
        cur_heap.add_to_queue(event(max_finish_time,FUNCTION_ARRIVAL,node))
        
        
def get_max_price(spot_price,demand_price,class_number):
    return spot_price + ((NUM_OF_MACHINES_CLASSES - class_number)/NUM_OF_MACHINES_CLASSES) *(demand_price-spot_price)

def get_new_vm_onspot(SOTA_2_Stats,type,cur_time,cost,vm_data,overall_events):
    vm=vm_data[type]
    new_vm = machine(type, vm.compute_power,vm.CPU,vm.memory,vm.reserve_cost,vm.ondemand_cost,0,None,None,None,0)
    new_vm.end_time = cur_time + 3600
    SOTA_2_Stats.total_spot_cost+=cost
    overall_events.add_to_queue(event(new_vm.end_time+1, MACHINE_END_TIME, new_vm))
    return new_vm

def get_new_vm_ondemand(SOTA_2_Stats,func_node,cur_time,vm_data,overall_events):

    
    for key,vm in vm_data.items():
        if(vm.memory >= func_node.memory):
            if cur_time + func_node.execution_time/vm.compute_power + func_node.cold_start_time/vm.compute_power > relative_function_deadline[func_node.id]:
                continue
            new_vm = machine(key, vm.compute_power,vm.CPU,vm.memory,vm.reserve_cost,vm.ondemand_cost,0,None,None,None,0)
            SOTA_2_Stats.ondemand_cost += vm.ondemand_cost
            new_vm.end_time = cur_time + 3600
            overall_events.add_to_queue(event(new_vm.end_time+1, MACHINE_END_TIME, new_vm))
            return new_vm
    
    # print("NO VM FOUND")
    return None 

from collections import defaultdict, deque
# Initialize deadlines dictionary
relative_function_deadline = {}
def compute_task_deadlines(nodes, edges, exec_times, cold_start_times, workflow_deadline):

    avg_exec_times = {node: (( exec_times[node] + cold_start_times[node]) / (AVG_VM_COMPUTE_POWER) ) for node in nodes}

    # Build the graph and initialize outdegrees
    graph = defaultdict(list)
    indegree = {node: 0 for node in nodes}
    outdegree = {node: 0 for node in nodes}
    
    for u, v,w in edges:
        graph[u].append(v)
        indegree[v] += 1
        outdegree[u] += 1

    # Collect all nodes with outdegree 0
    zero_outdegree_nodes = [node for node in nodes if outdegree[node] == 0]
    for node in zero_outdegree_nodes:
        relative_function_deadline[node] = workflow_deadline

    # Process nodes with outdegree 0 iteratively
    while zero_outdegree_nodes:
        new_zero_outdegree_nodes = []
        for node in zero_outdegree_nodes:
            # Update the deadlines of predecessors
            for predecessor in [u for u, v,w in edges if v == node]:
                deadline_for_node = relative_function_deadline[node] - avg_exec_times[node]
                if predecessor not in relative_function_deadline:
                    relative_function_deadline[predecessor] = deadline_for_node
                else:
                    relative_function_deadline[predecessor] = min(relative_function_deadline[predecessor], deadline_for_node)
                
                # Decrement outdegree and check if it becomes 0
                outdegree[predecessor] -= 1
                if outdegree[predecessor] == 0:
                    new_zero_outdegree_nodes.append(predecessor)
        
        # Move to the next set of nodes with outdegree 0
        zero_outdegree_nodes = new_zero_outdegree_nodes



def DS_SOTA2(taskMap,workflowMap,vm_data,compute_power=40):
    global QUEUE_TASK_COUNTER
    global relative_function_deadline
    global AVG_VM_COMPUTE_POWER
    AVG_VM_COMPUTE_POWER = compute_power
    ready_tasks = event_heap()
    overall_events = event_heap()
    function_deadline={}

    overall_events.add_to_queue(event(TASK_SCHEDULING_INTERVAL, TASK_SCHEDULING, 0))
    overall_events.add_to_queue(event(MACHINE_PROVISION_INTERVAL, MACHINE_PROVISION, 0))

    for workflow in list(workflowMap.values()):
        for node in workflow.start_nodes:
            node = int(node)
            overall_events.add_to_queue(event(workflow.arrival_time, FUNCTION_ARRIVAL,node))
            QUEUE_TASK_COUNTER+=1
        # print(workflow.arrival_time)
        # print(workflow.arrival_time + workflow.deadline)
        # print(len(workflow.nodes))
        # print(len(workflow.start_nodes))
        
        for node_id in workflow.nodes:
            function_deadline[node_id]=workflow.arrival_time+workflow.deadline
    

    idle_machines = []
    for i in range(NUM_OF_MACHINES_CLASSES):
        idle_machines.append([])

    df = pd.read_csv('../Dataset/spotprices.csv')

    for index, row in df.iterrows():
        if(row['price'] >= vm_data[row['instance_type']].ondemand_cost):
            continue 
        overall_events.add_to_queue(event(row['time'],SPOT_MACHINE_ARRIVAL, (row['instance_type'] , row['price'])))
    
    relative_function_deadline.clear()
    for workflow in list(workflowMap.values()):
        compute_task_deadlines(workflow.nodes, workflow.edges, {node: taskMap[node].execution_time for node in workflow.nodes}, {node: taskMap[node].cold_start_time for node in workflow.nodes}, workflow.arrival_time+workflow.deadline)
    

    global_finish_time = {}
    SOTA_2_Stats=wf_run_stats()
    machine_class={}
    busy_machines= []
    spot_machines_by_vm_type = {}
    total_busy_revokes = 0 
    total_free_revokes = 0 


    while(not overall_events.isempty() and QUEUE_TASK_COUNTER>0):
        current_event = overall_events.pop_from_queue()
        current_time = current_event.time
        event_type = current_event.type
        event_item = current_event.item

        if event_type == MACHINE_END_TIME:
            # print(f"MACHINE END TIME {current_time}")
            if event_item in idle_machines[machine_class[event_item.id]]:
                idle_machines[machine_class[event_item.id]].remove(event_item)
            else:
                overall_events.add_to_queue(event(current_time+10, MACHINE_END_TIME, event_item))

        if(event_type == FUNCTION_ARRIVAL):
            QUEUE_TASK_COUNTER-=1
            # print(f"FUNCTION ARRIVAL {current_time}")
            flag=0
            for par in taskMap[int(event_item)].parentids:
                if global_finish_time[par]==-1:
                    flag=1
                    break
            if flag==0:
                ready_tasks.add_to_queue(event_item)
        
        if(event_type == TASK_SCHEDULING):
            # print(f"TASK SCHEDULE {current_time}")
            # if ready_tasks.size()>0:
            #     print(ready_tasks.size())
            ready_tasks_classified = []
            for i in range(NUM_OF_TASK_CLASSES):
                ready_tasks_classified.append(event_heap())
            while(not ready_tasks.isempty()):
                task_id = ready_tasks.pop_from_queue()
                task = taskMap[task_id]
                task_class, slack_time = compute_class(task, current_time)   
                if task_class >=0:
                    ready_tasks_classified[task_class].add_to_queue((slack_time,task))
            
            for i in range(NUM_OF_TASK_CLASSES):

                while(not ready_tasks_classified[i].isempty()):
                    current_task= ready_tasks_classified[i].pop_from_queue()[1]
                    best_fit_machine = None
                    best_fit_memory = float('inf')  # start with a very large number
                    best_fit_machine_id = -1
                    
                    
                    exec_time = current_task.execution_time
                    cold_start_time = current_task.cold_start_time
                    task_hash = current_task.hashfunction
                    task_mem = current_task.memory
                    task_id = current_task.id
                    task_deadline = relative_function_deadline[task_id]

                    for j in range(0, i + 1):
                        for mch in idle_machines[j]:
                            if mch.memory < task_mem or mch.memory >= best_fit_memory:
                                continue  # Early memory filter (fastest check)

                            # Compute adjusted execution time based on cold start
                            is_cold_start = mch.last_hash_fun != task_hash
                            adjusted_time = exec_time / mch.compute_power + ((cold_start_time / mch.compute_power) if is_cold_start else 0)

                            estimated_end_time = current_time + adjusted_time

                            if estimated_end_time > mch.end_time or estimated_end_time > task_deadline:
                                continue  # Deadline or machine time constraint violation

                            # Passed all filters, track best fit
                            best_fit_machine = mch
                            best_fit_memory = mch.memory
                            best_fit_machine_id = j

                    
                    if best_fit_machine is None:
                        if i==0:
                            new_vm=get_new_vm_ondemand(SOTA_2_Stats,current_task,current_time,vm_data,overall_events)
                            # print(new_vm)
                            if new_vm==None:
                                # print(current_time, relative_function_deadline[current_task.id],current_task.execution_time,current_task.cold_start_time)
                                continue
                            machine_class[new_vm.id]=i
                            idle_machines[i].append(new_vm)
                            best_fit_machine = new_vm
                            best_fit_machine_id = i
                        else:
                            ready_tasks.add_to_queue(current_task.id)
                            continue
                    
                    idle_machines[best_fit_machine_id].remove(best_fit_machine)
                    
                    if best_fit_machine.last_hash_fun==current_task.hashfunction:
                        best_fit_machine.available_time = current_time+current_task.execution_time/(best_fit_machine.compute_power)
                    else:
                        best_fit_machine.available_time = current_time+current_task.execution_time/(best_fit_machine.compute_power) + current_task.cold_start_time/(best_fit_machine.compute_power)
                        best_fit_machine.last_hash_fun = current_task.hashfunction
                    best_fit_machine.running_function_id = current_task.id
                    best_fit_machine.running_worfklow_id = current_task.workflowid
                    global_finish_time[current_task.id] = best_fit_machine.available_time
                    busy_machines.append(best_fit_machine)
                    add_children_to_queue(current_task, overall_events, global_finish_time,taskMap)

                    overall_events.add_to_queue(event(best_fit_machine.available_time, MACHINE_FREEDOM, best_fit_machine))

            if(current_time <= END_TIME):
                overall_events.add_to_queue(event(current_time+TASK_SCHEDULING_INTERVAL, TASK_SCHEDULING, 0))
        
        if event_type==MACHINE_FREEDOM:
            # print(f"MACHINE FREEDOM {current_time}")
            if event_item in busy_machines:
                busy_machines.remove(event_item)
                idle_machines[machine_class[event_item.id]].append(event_item)

        
        if event_type == MACHINE_PROVISION:
            # print(f"MACHINE PROVISION {current_time}")
            ready_tasks_classified = []
            for i in range(NUM_OF_TASK_CLASSES):
                ready_tasks_classified.append(event_heap())
                
            for task_id in ready_tasks.items:
                task = taskMap[task_id]
                task_class, slack_time = compute_class(task, current_time)
                if task_class >=0:
                    ready_tasks_classified[task_class].add_to_queue((-task.memory,task))
            
            for sublist in idle_machines:
                sublist.sort(key=lambda machine: machine.memory,reverse=True)
            requirements=[]
            mptr = 0
            i=0
            while(not ready_tasks_classified[i].isempty() ):
                current_task= ready_tasks_classified[i].pop_from_queue()[1]
                if(mptr >= len(idle_machines[i])):
                    requirements.append(current_task)
                    continue 
                if(current_task.memory > idle_machines[i][mptr].memory):
                    requirements.append(current_task)
                else:
                    mptr+=1
                
            # continue
                
            
            for task in requirements:
                new_vm=get_new_vm_ondemand(SOTA_2_Stats,task,current_time,vm_data,overall_events)
                if new_vm is None:
                    continue
                machine_class[new_vm.id]=i
                idle_machines[i].append(new_vm)
            if(current_time <= END_TIME):
                overall_events.add_to_queue(event(current_time+MACHINE_PROVISION_INTERVAL, MACHINE_PROVISION, 0))
                
        
        if event_type==SPOT_MACHINE_ARRIVAL:
            # print(f"SPOT MACHINE ARRIVAL {current_time}")
            ready_tasks_classified = []
            new_spot_tuple = []
            
            for spot_tup in spot_machines_by_vm_type.get(event_item[0],[]):
                if current_time - spot_tup[1] < 3600:
                    if event_item[1] <= spot_tup[2]:
                        new_spot_tuple.append(spot_tup) 
                    else:
                        for i in range(NUM_OF_MACHINES_CLASSES):
                            for vm in idle_machines[i]:
                                if vm.id==spot_tup[0]:
                                    SOTA_2_Stats.total_spot_cost-=spot_tup[2]*( 3600 - current_time + spot_tup[1])/3600
                                    idle_machines[i].remove(vm)
                                    total_free_revokes+=1

                    for vm in busy_machines:
                            if vm.id == spot_tup[0]:
                                busy_machines.remove(vm)
                                total_busy_revokes+=1
                                QUEUE_TASK_COUNTER+=1
                                overall_events.add_to_queue(event(current_time,FUNCTION_ARRIVAL,vm.running_function_id))
                                global_finish_time[vm.running_function_id] = -1
                                SOTA_2_Stats.total_spot_cost-=spot_tup[2]*( 3600 - current_time + spot_tup[1])/3600
                        


            spot_machines_by_vm_type[event_item[0]] = new_spot_tuple
            for i in range(NUM_OF_TASK_CLASSES):
                ready_tasks_classified.append(event_heap())
                
            for task_id in ready_tasks.items:
                task = taskMap[task_id]
                task_class, slack_time = compute_class(task, current_time)
                if task_class >=0:
                    ready_tasks_classified[task_class].add_to_queue((-task.memory,task))
            
            for sublist in idle_machines:
                sublist.sort(key=lambda machine: machine.memory,reverse=True)
            no_of_machines_rented=0
            spot_machine=vm_data[event_item[0]]
            for i in range(NUM_OF_TASK_CLASSES):
                requirements=[]
                mptr = 0
                while(not ready_tasks_classified[i].isempty() ):
                    current_task= ready_tasks_classified[i].pop_from_queue()[1]
                    if(mptr >= len(idle_machines[i])):
                        requirements.append(current_task)
                        continue 
                    if(current_task.memory > idle_machines[i][mptr].memory):
                        requirements.append(current_task)
                    else:
                        mptr+=1
                
                # continue
                
                if i==0:
                    for task in requirements:
                        new_vm=get_new_vm_ondemand (SOTA_2_Stats,task,current_time,vm_data,overall_events)
                        if new_vm is None:
                            continue
                        machine_class[new_vm.id]=i
                        idle_machines[i].append(new_vm)
                    continue    
                
                # continue
                
                bid_price=get_max_price(event_item[1],spot_machine.ondemand_cost,i)
                
                # continue
                
                for task in requirements:
                    if no_of_machines_rented>=SPOT_THRESHOLD:
                        break
                    if task.memory <= spot_machine.memory:
                        if current_time + task.execution_time/spot_machine.compute_power + task.cold_start_time/spot_machine.compute_power > relative_function_deadline[task.id]:
                            continue
                        new_vm=get_new_vm_onspot(SOTA_2_Stats,event_item[0],current_time,bid_price,vm_data,overall_events)
                        machine_class[new_vm.id]=i
                        idle_machines[i].append(new_vm)
                        no_of_machines_rented+=1
                        spot_machines_by_vm_type[event_item[0]].append((new_vm.id,current_time,bid_price))
                
    
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
            # print(workflow.reward)
            # print(max_finish_time)
            continue
        if max_finish_time <= workflow.arrival_time+workflow.deadline:
        
            SOTA_2_Stats.total_reward+=workflow.reward
        else:
            total_deadlines_missed+=1
 

    total_cost=SOTA_2_Stats.ondemand_cost + SOTA_2_Stats.total_spot_cost

    return "D+S_SOTA2",0,SOTA_2_Stats.ondemand_cost,SOTA_2_Stats.total_spot_cost, total_cost,SOTA_2_Stats.total_reward,SOTA_2_Stats.total_reward-total_cost,total_deadlines_missed