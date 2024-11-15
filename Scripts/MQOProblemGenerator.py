#!/usr/bin/env python
# coding: utf-8

# In[1]:


import numpy as np
import json
import os
import pickle
import pathlib
import itertools

import MQOQUBOGenerator as MQOQUBOGenerator
import DataUtil as DataUtil
from dadk.QUBOSolverDAv2 import QUBOSolverDAv2
from dadk.QUBOSolverCPU import *
import time
from math import inf


# In[2]:


def save_to_csv(data, path, filename):
    sd = os.path.abspath(path)
    pathlib.Path(sd).mkdir(parents=True, exist_ok=True) 
    
    f = open(path + '/' + filename, 'a', newline='')
    writer = csv.writer(f)
    writer.writerow(data)
    f.close()


def load_data(path, filename):
    datafile = os.path.abspath(path + '/' + filename)
    if os.path.exists(datafile):
        with open(datafile, 'rb') as file:
            return json.load(file)
        
def load_all_results(path):
    if not os.path.isdir(path):
        return []
    onlyfiles = [f for f in listdir(path) if isfile(join(path, f))]
    data = []
    for datafile in onlyfiles:
        with open(path + '/' + datafile, 'rb') as file:
            data.append(json.load(file))
    return data

def save_data(data, path, filename):
    print(path)
    datapath = os.path.abspath(path)
    pathlib.Path(datapath).mkdir(parents=True, exist_ok=True) 
    
    datafile = os.path.abspath(path + '/' + filename)
    mode = 'a' if os.path.exists(datafile) else 'w'
    with open(datafile, mode) as file:
        json.dump(data, file)


# In[3]:


def sample_uniform(min_val=1, max_val=10, size=1, scalar=1):
    return np.random.randint(min_val, max_val, size=size, dtype=int) * scalar

def get_query_for_plan(plan_index, plans_per_query):
    return plan_index // plans_per_query



# In[5]:

def generate_MQO_problem(num_queries, num_plans_per_query, qubo_density, cost_scaling=0):
    num_plans = num_queries * num_plans_per_query
    savings_candidates = list(x for x in itertools.combinations(np.arange(num_plans), 2) if int(x[0]/num_plans_per_query) != int(x[1]/num_plans_per_query))
    
    queries = {}
    plan_costs = []
    
    offset = cost_scaling

    min_cost_val = 1 + offset
    max_cost_val = 20 + offset
    
    plan_costs = sample_uniform(min_val=min_cost_val, max_val=max_cost_val, size=int(num_queries*num_plans_per_query), scalar=1).tolist()
    
    for q in range(num_queries):
        queries[q] = []
        for p in range(num_plans_per_query):
            queries[q].append(q*num_plans_per_query + p)

    num_quadratic_terms = ((num_plans_per_query*(num_plans_per_query-1))/2)*num_queries
    num_quadratic_terms_total = (num_plans*(num_plans-1))/2
    
    total_num_savings = int(num_quadratic_terms_total) - int(num_quadratic_terms)
    num_savings = int(total_num_savings*qubo_density)
    savings = []
    
    if num_savings >= 1:
        plan_pair_indices = np.random.choice(len(savings_candidates), num_savings, replace=False)
        plan_pairs = np.array(savings_candidates)[plan_pair_indices]
        savings_vals = sample_uniform(size=num_savings)
        for i in range(len(plan_pairs)):
            savings.append([[int(plan_pairs[i][0]), int(plan_pairs[i][1])], int(savings_vals[i])])
    else:
        print("Density too small - no savings")
        return 
    
    savings = sorted(savings)
    return queries, plan_costs, savings