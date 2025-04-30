import random
import datetime
import csv
# from Task import task 
# from Workflow import workflow
# from Machine import machine
from helper_classes import * 
import numpy as np
import networkx as nx
# test_wf_set = {"Montage_25", "Epigenomics_24","Inspiral_30", "CyberShake_100","Inspiral_100" ,"Montage_100" }
test_wf_set = {"Montage_25","Epigenomics_24","Montage_50","Montage_100","CyberShake_50" ,"CyberShake_100", "Inspiral_30","Inspiral_50","Inspiral_100" }
# test_wf_set= {"Montage_25"}
COLD_START_PERCENT=0.25
MEM_SCALE_FACTOR=1.2
DATASET_PATH = "../Dataset/Parsed/"

def compute_depths(graph):
    depths = {node: 0 for node in graph.nodes()}
    for node in reversed(list(nx.topological_sort(graph))):
        depths[node] = max((depths[succ] + 1 for succ in graph.successors(node)), default=0)
    return depths

def distribute_rewards(nodes, edges, total_reward,taskMap, lambda_param=0.1):
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from((u, v) for u, v, _ in edges)  # Ignore edge weights for now
    
    depths = compute_depths(graph)
    # end_node = max((node for node in graph.nodes() if graph.out_degree(node) == 0), key=lambda n: depths[n])
    
    weights = {node: taskMap[node].execution_time * np.exp(lambda_param * depths[node]) for node in graph.nodes()}
    total_weight = sum(weights.values())
    rewards = {node: (total_reward * weights[node] / total_weight) for node in graph.nodes()}
    # r = 0 
    for key,val in rewards.items():
        taskMap[key].reward = val 
        # print(f"{key : }  {val }")
        # r+=val
    # print(r , total_reward)
    # return rewards

# Example Usage:
# nodes = ["A", "B", "C", "D"]
# edges = [("A", "B", 1.5), ("A", "C", 2.0), ("B", "D", 1.2), ("C", "D", 1.8)]  # Edge weights are ignored for now
# execution_times = {"A": 2, "B": 3, "C": 4, "D": 5}
# total_reward = 100

# reward_distribution = distribute_rewards(nodes, edges, execution_times, total_reward, lambda_param=0.1)
# print(reward_distribution)

# Example Usage:
# nodes = ["A", "B", "C", "D"]
# edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]
# execution_times = {"A": 2, "B": 3, "C": 4, "D": 5}
# total_reward = 100

# print(reward_distribution)
def parse_txt_to_wf(workflowname, workflowid, arrival_time, predicted_arrival_time, taskMap, workflowMap):
    
    txt_filename = DATASET_PATH + workflowname + ".txt"
    with open(txt_filename, 'r') as file:
        lines = file.readlines()
    
    # Read metadata
    n, rel_constraint, deadline = map(float, lines[0].split())
    n = int(n)
    graph = {
        "nodes": {},  # Stores {node: {'wcec': int, 'deadline': int}}
        "edges": []  # Stores edges as (src, dest, weight)
    }
    
    tasks = []
    edges_set = []
    edge_weights = {}  # To store total edge weights for each node (incoming + outgoing)
    # graph_nodes = []
    # graph_edges =[]
    # Initialize edge weights for each node
    for i in range(n):
        edge_weights[i] = 0
        # graph_nodes.append(i)
    # Process tasks and edges

    total_length = 0
    for i in range(n):  # Nodes are numbered from 0 to n-1
        parts = lines[i+1].split()
        func_name = parts[0]
        parts = list(map(float, parts[1:]))
        # print(func_name)
        wcec = 120*parts[0]  # Worst-case execution time
        total_length+=wcec
        num_edges = int(parts[1])  # Number of outgoing edges
        edges = parts[2:]  # List of child nodes and edge weights
        
        # deadline of task node not yet known, will be known while running algorithm
        new_task = task(func_name, workflowid, 0, wcec, wcec * COLD_START_PERCENT, arrival_time, predicted_arrival_time, -1, [], [])
        tasks.append(new_task.id)
        taskMap[new_task.id] = new_task



    for i in range(n):
        # Process outgoing edges
        parts = lines[i+1].split()
        parts = list(map(float, parts[1:]))
        wcec = 120*parts[0]  # Worst-case execution time
        num_edges = int(parts[1])  # Number of outgoing edges
        edges = parts[2:]  # List of child nodes and edge weights
        # print(f"len_edges  {len(edges)}" )
        for j in range(0, len(edges), 2):
            child_node = int(edges[j])  # Child node index
            edge_weight = edges[j + 1]  # Edge weight (data to be transferred)
            # print(f"edge_weight {edge_weight}")
            # Add edge to edges_set
            # print(child_node)
            # graph_edges.append((tasks[i]))
            edges_set.append((tasks[i], tasks[child_node], edge_weight))
            taskMap[tasks[i]].children.append(tasks[child_node]) 
            taskMap[tasks[child_node]].parentids.append(tasks[i])
            # Update edge weights for source and destination nodes
            edge_weights[i] += edge_weight  # Outgoing edge weight for source node
            edge_weights[child_node] += edge_weight  # Incoming edge weight for child node

    min_weight = min(edge_weights.values())
    max_weight = max(edge_weights.values())
    # print(f"min_weight {min_weight}, max_weight: {max_weight}")
    for i in range(n):
        if max_weight == min_weight:
            # If all weights are the same, set normalized value to 128 (middle of the range)
            normalized_memory = 128
        else:
            # Normalize using the formula
            normalized_memory = ((edge_weights[i] - min_weight) / (max_weight - min_weight)) * 230
        taskMap[tasks[i]].memory = normalized_memory
        
    # Create the workflow object
    deadline_range = random.uniform(0.09, 0.11)  
    new_workflow = workflow(workflowid, workflowname,100*deadline*deadline_range, 0, arrival_time, predicted_arrival_time, workflow.get_reward(predicted_arrival_time, 100*deadline/1.5, total_length,deadline_range), tasks, edges_set)
    populate_start_nodes(new_workflow)
    workflowMap[workflowid] = new_workflow
    # print(new_workflow)
    distribute_rewards(tasks, edges_set, new_workflow.reward,taskMap, lambda_param=0.1)
    



def generate_workflow_arrival_times(num_instances, output_csv, taskMap, workflowMap):
    start_time = datetime.datetime.combine(datetime.date.today(), datetime.time(0, 0)).timestamp()  # Midnight (12 AM)
    end_time = datetime.datetime.combine(datetime.date.today(), datetime.time(23, 59)).timestamp()  # 11:59 PM


    # Generate actual arrival times within the day
    actual_arrival_times = sorted([
        start_time + random.randint(0, int(end_time - start_time)) for _ in range(num_instances)
    ])
    
    # Generate predicted arrival times with small deviation (Gaussian noise)
    mean = 0
    stddev = 0

    # if stddev == 0:


    predicted_arrival_times = [
        max(start_time, min(end_time, actual + random.gauss(mean, stddev)))  
        for actual in actual_arrival_times
    ]
    # else:
    #     predicted_arrival_times = [
    #         max(start_time, min(end_time, actual + mean))  
    #         for actual in actual_arrival_times
    #     ]
    
    # Process each workflow instance
    for i, (actual, predicted) in enumerate(zip(actual_arrival_times, predicted_arrival_times)):
        cur_workflow = random.choice(list(test_wf_set))
        parse_txt_to_wf(cur_workflow, i, actual - start_time, predicted - start_time, taskMap, workflowMap)  # Convert to seconds since 12 AM
    # print(f"TEST SET : {test_wf_set}")
        
def parse_vm_csv():
    vm_data = {}

    with open("../Dataset/pricing.csv", 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            instance_type = row['instance_type']
            memory_per_cpu = float(row['memory_per_cpu'])
            vcpus = int(row['vcpus'])
            clock_speed = float(row['clock_speed'])
            on_demand_price = float(row['on_demand_price'])
            reserve_price = float(row['reserve_price'])
            new_vm = machine(instance_type, clock_speed*vcpus, vcpus ,memory_per_cpu*vcpus, reserve_price,on_demand_price,0,0,0,0,0)
            vm_data[instance_type] = new_vm
    return vm_data


def populate_start_nodes(workflow):
    in_degree = {node: 0 for node in workflow.nodes}
    # Count in-degrees based on edges
    for _, to_node,wt in workflow.edges:
        if int(to_node) in in_degree:
            in_degree[int(to_node)] += 1
    # Find nodes with in-degree 0
    workflow.start_nodes = [node for node, degree in in_degree.items() if degree == 0]