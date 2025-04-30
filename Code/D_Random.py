from helper_classes import *
import random
FUNCTION_ARRIVAL = 0 
MACHINE_RESERVE = 1 
RESERVE = 0 
DEMAND = 1 


def machine_sanity_check(free_machines, busy_machines,cur_time):
    for vm in free_machines:
        # Removing those machines which have expired their total time
        if(vm.end_time <= cur_time):
            free_machines.remove(vm)
            
    for vm in busy_machines:
        # Removing those machines which have expired their total time
        if(vm.end_time<=cur_time ):
            busy_machines.remove(vm)
            continue 
        # Adding machines that have finished their work to the free machines list
        if(vm.available_time <= cur_time):
            busy_machines.remove(vm)
            free_machines.append(vm)
            
            
def get_new_vm(Stats,func_node,type,cur_time,vm_data):
    
    # Returns least memory vm that has enough memory for this task 
    vm_list=[]
    for key,vm in vm_data.items():
        if(vm.memory >= func_node.memory):
            vm_list.append((key,vm))
    
    if(len(vm_list) == 0):
        # print("NO VM FOUND")
        return None
    
    key, vm = random.choice(vm_list)
    new_vm = machine(key, vm.compute_power,vm.CPU,vm.memory,vm.reserve_cost,vm.ondemand_cost,0,None,None,None,0)
    if(type==RESERVE):
    #    print(f"RESERVE : {vm.reserve_cost}  {new_vm}")
        Stats.reserve_cost += vm.reserve_cost
    else :
    #    print(f"DEMAND  : {vm.ondemand_cost}  {new_vm}")
        Stats.ondemand_cost += vm.ondemand_cost
            
    new_vm.end_time = cur_time + 3600
            
    return new_vm
    
    # print("NO VM FOUND")
    # return None 




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

def D_Random(taskMap,workflowMap,vm_data):
    incoming_tasks = event_heap()

    for workflow in list(workflowMap.values()):

        for node in workflow.start_nodes:
            node = int(node)
            incoming_tasks.add_to_queue(event(workflow.arrival_time, FUNCTION_ARRIVAL,node))
    

    free_machines= []
    busy_machines= []
    global_finish_time = {}
    Rand_without_cold_start_Stats = wf_run_stats()

    while(not incoming_tasks.isempty()):
        cur_top_element = incoming_tasks.pop_from_queue()
        cur_node_id = cur_top_element.item
        cur_time = cur_top_element.time
        cur_node = taskMap[cur_node_id]
        
        # Removes Expired machines and updates status of machines
        machine_sanity_check(free_machines,busy_machines,cur_time)
        suitable_vms = []
        for ind in range(0,len(free_machines)):
            vm = free_machines[ind]
            time_on_this_vm = cur_node.execution_time / vm.compute_power
            if(vm.last_hash_fun != cur_node.hashfunction):
                time_on_this_vm += cur_node.cold_start_time/vm.compute_power
            if(vm.memory >= cur_node.memory and vm.end_time > (cur_time + time_on_this_vm) ):
                suitable_vms.append(ind)
        
        time_on_this_vm = 0
        if(len(suitable_vms) ==0):
            new_vm = get_new_vm(Rand_without_cold_start_Stats,cur_node,DEMAND,cur_time,vm_data)
            time_on_this_vm = cur_node.execution_time/new_vm.compute_power + cur_node.cold_start_time/new_vm.compute_power
            update_machine(new_vm,cur_node,cur_time,time_on_this_vm)
            busy_machines.append(new_vm)

        else:
            
            chosen_vm_ind = random.choice(suitable_vms) 
            my_vm = free_machines[chosen_vm_ind]
            free_machines.pop(chosen_vm_ind) 
            time_on_this_vm = cur_node.execution_time/my_vm.compute_power + cur_node.cold_start_time/my_vm.compute_power
            update_machine(my_vm,cur_node,cur_time,time_on_this_vm)
            busy_machines.append(my_vm)
        
        global_finish_time[cur_node_id] = cur_time + time_on_this_vm
        add_children_to_queue(cur_node,incoming_tasks,global_finish_time,taskMap)
    
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
        
        
            Rand_without_cold_start_Stats.total_reward+=workflow.reward 
        else:
            total_deadlines_missed+=1

    total_cost=Rand_without_cold_start_Stats.ondemand_cost
    print(total_deadlines_missed)
    return "D_Random",0,Rand_without_cold_start_Stats.ondemand_cost,0,total_cost,Rand_without_cold_start_Stats.total_reward,Rand_without_cold_start_Stats.total_reward-total_cost,total_deadlines_missed

