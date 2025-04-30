from helper_classes import *
import pandas as pd
FUNCTION_ARRIVAL = 3 
MACHINE_RESERVE = 0 
MACHINE_NOT_RESERVE = 2
SPOT_MACHINE_ARRIVAL =1  
RESERVE = 0 
DEMAND = 1 
AVG_VM_COMPUTE_POWER = 13


def get_priority(vm,cur_time,function_total_alive_containers,taskMap):
    if taskMap.get(vm.running_function_id,0) ==0 : 
        return -cur_time +vm.available_time + 30*(vm.memory/256.0)+ 100*((1.4+0.3*function_total_alive_containers.get(vm.last_hash_fun,0))* 1)/(vm.compute_power)
    return -cur_time +vm.available_time + 30*(vm.memory/256.0)+ 100*((1.4+0.3*function_total_alive_containers.get(vm.last_hash_fun,0))* taskMap.get(vm.running_function_id,0).cold_start_time)/(vm.compute_power)


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
                if arr_time+curr_task.execution_time/(vm.compute_power) + curr_task.cold_start_time/vm.compute_power<=vm.end_time and arr_time+curr_task.execution_time/(vm.compute_power) + curr_task.cold_start_time/(vm.compute_power) <= relative_function_deadline[curr_task.id]:
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
    
    
def add_children_to_queue(cur_node , cur_heap , global_finish_time,taskMap):
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
      
        cur_heap.add_to_queue(event(max_finish_time,FUNCTION_ARRIVAL,node))

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




def D_DCD(taskMap,workflowMap,vm_data,avg_vm_compute_power=40):
    global AVG_VM_COMPUTE_POWER

    global relative_function_deadline

    AVG_VM_COMPUTE_POWER = avg_vm_compute_power
    
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
        compute_task_deadlines(workflow.nodes, workflow.edges, {node: taskMap[node].execution_time for node in workflow.nodes}, {node: taskMap[node].cold_start_time for node in workflow.nodes},workflow.arrival_time, workflow.arrival_time+workflow.deadline)
    

    global_finish_time = {}
    function_ran = 0
    machine_count = {}
    free_machines = []
    busy_machines = []
    vm_schedule = []
    spot_machines = {}
    function_total_alive_containers = {}
    R_D_S_Stats = wf_run_stats()
    mem_list = []
    for vm in vm_data.values():
        mem_list.append(vm.memory)
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
        

        cur_node_id = cur_top_element.item
        cur_node = taskMap[cur_node_id]
        machine_sanity_check(free_machines,busy_machines,cur_time,function_total_alive_containers)
        best_vm_index = choose_vm(free_machines,cur_node,mem_list,function_total_alive_containers,cur_time,taskMap)
        
        time_on_this_vm = 0
        if(best_vm_index ==None):
            new_vm = get_new_vm(R_D_S_Stats,cur_node,DEMAND,cur_time,cur_time,cur_node,vm_data)
            # print(f"DEMAND : {cur_time}  {new_vm.type} {new_vm.ondemand_cost}")
            if(new_vm == None):
                # Task Skipped because no machine is fast enough 
                continue 
            to_be_rem = -1
                    
            time_on_this_vm = cur_node.execution_time/new_vm.compute_power + cur_node.cold_start_time/new_vm.compute_power
            update_machine(new_vm,cur_node,cur_time,time_on_this_vm)
            busy_machines.append(new_vm)
            
        else:

            chosen_vm_ind = best_vm_index
            my_vm = free_machines[chosen_vm_ind]

            free_machines.pop(chosen_vm_ind) 
            time_on_this_vm = cur_node.execution_time / my_vm.compute_power
            if(my_vm.last_hash_fun != cur_node.hashfunction):
                time_on_this_vm += cur_node.cold_start_time /my_vm.compute_power
            update_machine(my_vm,cur_node,cur_time,time_on_this_vm)
            busy_machines.append(my_vm)
        
        global_finish_time[cur_node_id] = cur_time + time_on_this_vm
        add_children_to_queue(cur_node,overall_events,global_finish_time,taskMap)

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
        
            R_D_S_Stats.total_reward+=workflow.reward
        else:
            total_deadlines_missed+=1

    total_cost=R_D_S_Stats.ondemand_cost
    return "D_DCD",0,R_D_S_Stats.ondemand_cost,0,total_cost,R_D_S_Stats.total_reward,R_D_S_Stats.total_reward-total_cost,total_deadlines_missed

