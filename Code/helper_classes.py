import heapq
from sortedcontainers import SortedList
import bisect


class wf_run_stats:
    
    def __init__(self):
        self.total_cost  = 0 
        self.ondemand_cost = 0 
        self.reserve_cost = 0
        self.total_cold_start_time = 0
        self.total_cold_start_count = 0
        self.total_spot_cost = 0 
        self.total_reward = 0 
        self.total_reserve_opportunities=0
        self.total_reserves=0

class event:
    
    def __init__(self, time,type,item):
        
        self.time = time 
        self.type = type
        self.item = item 
        # print(type(time))
        # print(type(self.time))
    def __lt__(self,other):
        if self.time == other.time:
            # print(type(self.time))
            return self.type < other.type
        return self.time < other.time
class event_heap:

    def __init__(self):
        self.items=[]
    
    def add_to_queue(self,val):
    # Push a tuple (arrival_time, function_obj) onto the heap
        heapq.heappush(self.items, val)

# Pop an item from the priority queue (it will return the item with the smallest arrival time)
    def pop_from_queue(self):
        if self.items:
            # Pop the item with the smallest arrival time
            return heapq.heappop(self.items)
        else:
            return None  # Return None if the queue is empty

    # Peek at the item with the smallest arrival time without popping it
    def peek_queue(self):
        if self.items:
            return self.items[0]
        else:
            return None
    
    def isempty(self):
        return len(self.items)==0
    
    def size(self):
        return len(self.items)
        


class machine:
    
    id_counter=0
    def __init__(self ,type, compute_power,CPU ,memory,reserve_cost,ondemand_cost,available_time ,last_hash_fun,running_function_id ,running_worfklow_id,end_time = 0):
        # self.instance_type = instance_type
        self.id = machine.id_counter
        self.type = type 
        self.compute_power = compute_power
        self.CPU = CPU
        self.memory = memory
        self.reserve_cost = reserve_cost
        self.ondemand_cost = ondemand_cost
        self.available_time = available_time # absolute time at which current task or previous task finishes
        self.last_hash_fun = last_hash_fun
        self.running_function_id = running_function_id
        self.running_worfklow_id = running_worfklow_id
        self.end_time=end_time  # absolute renting end time of the virtual machine
        # self.
        machine.id_counter+=1

    
    def __repr__(self):
        return f"Machine(ComputePower: {self.compute_power}, CPU: {self.CPU}, Memory: {self.memory} GB, Cost: {self.reserve_cost}  {self.ondemand_cost}, AvailableTime: {self.available_time}, LastHashFunction: {self.last_hash_fun}, RunningFunctionId: {self.running_function_id}, RunningWorkflowId: {self.running_worfklow_id})"
        
        
        
class task:

    id_counter = 0

    """The following are set when this task node is enqueued in the algorithm

        1. workflowid
        2. arrival_time
        3. predicted_arrival_time
        4. deadline
    
    """
    def __init__(self , hashfunction, workflowid, memory, execution_time, cold_start_time, arrival_time=0,predicted_arrival_time=0, deadline=0 , parentids=[] , children=[]):
        self.id = task.id_counter
        self.hashfunction = hashfunction
        self.workflowid = workflowid
        self.memory = memory
        self.execution_time = execution_time
        self.cold_start_time = cold_start_time
        self.arrival_time = arrival_time
        self.predicted_arrival_time = predicted_arrival_time
        self.deadline = deadline
        self.parentids = parentids
        self.children = children
        self.reward = 0 
        task.id_counter = task.id_counter + 1
        # self.reward = reward
    
    def __repr__(self):
        return str(self.__dict__)
    
    def __lt__(self, other):
        return True


class workflow :
    

    
    def __init__(self,id,type, deadline, length, arrival_time, predicted_arrival_time, reward, nodes, edges, start_nodes=[],max_fin_time = -1 ):
        self.id = id
        self.type = type
        self.deadline = deadline
        self.length = length
        self.arrival_time = arrival_time
        self.predicted_arrival_time = predicted_arrival_time
        self.reward = reward
        self.nodes = nodes
        self.edges = edges
        self.start_nodes = start_nodes
        self.max_fin_time = max_fin_time
        

   
    def __repr__(self):
        return f"ID: {self.id }, Type: {self.type},  Deadline: {self.deadline}, Length: {self.length}, ArrivalTime: {self.arrival_time}, PredArrivalTime : {self.predicted_arrival_time}, Reward: {self.reward}, Nodes: {self.nodes}, Edges: {self.edges}, StartNodes: {self.start_nodes}, MaxFinTime: {self.max_fin_time})"
    
    @staticmethod
    def get_reward(arrival_time , critical_path, total_length,deadline_range):
    
    
        REWARD_SCALE_CONSTANT = 0.0000001
        minimum_deadline = 0.03
    # if slack_time <= 0:
    #     return 0  # Avoid division by zero or undefined cases

        # slack_time =  (arrival_time - length)
        # scale_factor/= length

        # Adjusted reward formula
        # print(deadline_range - minimum_deadline)
        # print(critical_path)
        # reward = REWARD_SCALE_CONSTANT *pow(total_length/(critical_path*(deadline_range-minimum_deadline)) ,2) *total_length
        reward = REWARD_SCALE_CONSTANT *pow(total_length/(critical_path) ,2) *total_length
        return reward
    
    
    

class CumulativeScore:
    def __init__(self):
        self.data = SortedList()  # Stores (time, cumulative_score)
        self.scores = {}  # Stores actual score for each time

    def add_pair(self, time, score):
        """Insert a new (time, score) and maintain cumulative sum."""
        if time in self.scores:
            return  # Avoid duplicate times

        prev_sum = self.data[-1][1] if self.data else 0
        new_sum = prev_sum + score
        self.data.add((time, new_sum))
        self.scores[time] = score

    def query(self, start, end):
        """Find total score in time range [start, end]."""
        if not self.data:
            return 0

        # Find index of first element ≥ start
        left_idx = bisect.bisect_left(self.data, (start, 0))
        # Find index of last element ≤ end
        right_idx = bisect.bisect_right(self.data, (end, float('inf'))) - 1

        if right_idx < 0 or left_idx >= len(self.data):
            return 0

        total = self.data[right_idx][1] - (self.data[left_idx-1][1] if left_idx > 0 else 0)
        return total