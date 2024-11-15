#!/usr/bin/env python
# coding: utf-8

# In[1]:


import numpy as np
import json
import os
import pickle
import pathlib
import itertools

import Scripts.MQOQUBOGenerator as MQOQuboGenerator
import Scripts.DataExport as DataExport
import Scripts.DataUtil as DataUtil
import time
from math import inf
import neal


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

def save_data(data, path, filename, override=True):
    print(path)
    datapath = os.path.abspath(path)
    pathlib.Path(datapath).mkdir(parents=True, exist_ok=True) 
    
    datafile = os.path.abspath(path + '/' + filename)
    if os.path.exists(datafile):
        if override:
            try:
                os.remove(datafile)
            except OSError:
                pass
        else:
            return
    mode = 'a' if os.path.exists(datafile) else 'w'
    with open(datafile, mode) as file:
        json.dump(data, file)




def evaluate_mqo_solution(active_plans, plan_costs, num_plans_per_query, savings):
    active_savings = 0
    
    for (p1, p2) in itertools.combinations(active_plans, 2):
        # Verify validity
        if int(p1 / num_plans_per_query) == int(p2 / num_plans_per_query):
            return False
        if (p1, p2) in savings:
            active_savings += savings[(p1, p2)]
        #active_savings += savings[p1][p2]
    
    costs = sum(plan_costs[x] for x in active_plans)
    return costs - active_savings


# In[5]:


def solve_problem(qubo, number_runs=100, number_iterations=1000):
    
    sampler = neal.SimulatedAnnealingSampler()
    start = time.time()
    result = sampler.sample(qubo, num_reads=number_runs, num_sweeps=number_iterations, answer_mode='raw')
    opt_time = time.time() - start
    opt_time_in_ms = opt_time * 1000
    
    solutions = []
    for item in result.record:
        bitstring = [int(x) for x in item[0]]
        solutions.append([bitstring, int(item[2]), float(item[1])])
        
    return solutions, opt_time_in_ms

def conduct_experiment(num_queries_list, num_plans_per_query_list, density_list, problems, pruning_density_list, num_runs, num_iterations_list, problem_path_prefix, result_path_prefix, max_num_samples=20, timeout_in_ms=60000):
    for num_queries in num_queries_list:
        for num_plans_per_query in num_plans_per_query_list:
            for (density, cost_scaling) in density_list:
                #for cost_scaling in cost_scaling_list:
                for i in problems:
                    problem_path = problem_path_prefix + '/' + str(num_queries) + '_queries/' + str(num_plans_per_query) + '_ppq/density_' + str(density) + '/cost_scaling_' + str(cost_scaling) + '/problem_' + str(i)
                    queries = DataUtil.load_compressed_data(problem_path, 'queries.txt')
                    plan_costs = DataUtil.load_compressed_data(problem_path, 'plan_costs.txt') 
                    savings = DataUtil.load_compressed_data(problem_path, 'savings_list.txt')

                    for pruning_density in pruning_density_list:
                        qubo = MQOQuboGenerator.generate_DWave_QUBO(queries, plan_costs, savings, pruning_density=pruning_density)
                        for num_iterations in num_iterations_list:
                            total_annealing_time = 0
                            sample_index = 0
                            while sample_index < max_num_samples and total_annealing_time < timeout_in_ms:
                                result_path = result_path_prefix + '/' + str(num_queries) + '_queries/' + str(num_plans_per_query) + '_ppq/density_' + str(density) + '/cost_scaling_' + str(cost_scaling) + '/problem_' + str(i) + '/' + 'pruning_density_' + str(pruning_density) + '/' + str(num_runs) + '_runs/' + str(num_iterations) + '_iterations/sample_' + str(sample_index)
                                solutions, opt_time = solve_problem(qubo, number_runs=num_runs, number_iterations=num_iterations)
                                total_annealing_time = total_annealing_time + opt_time
                                save_data([solutions, float(opt_time)], result_path, "response.txt") 
                                sample_index = sample_index + 1 
                                                   
            
def export_results(num_queries_list, num_plans_per_query_list, density_list, problems_list, pruning_density_list, samples_list, num_runs, num_iterations_list, problem_path_prefix, data_path_prefix, result_path_prefix):
    for num_queries in num_queries_list:
        for num_plans_per_query in num_plans_per_query_list:
            for (density, cost_scaling) in density_list:
                #for cost_scaling in cost_scaling_list:
                for p in problems_list:
                    problem_path = problem_path_prefix + '/' + str(num_queries) + '_queries/' + str(num_plans_per_query) + '_ppq/density_' + str(density) + '/cost_scaling_' + str(cost_scaling) + '/problem_' + str(p)

                    queries = DataUtil.load_compressed_data(problem_path, 'queries.txt')
                    plan_costs = DataUtil.load_compressed_data(problem_path, 'plan_costs.txt') 
                    savings_list = DataUtil.load_compressed_data(problem_path, 'savings_list.txt')
                    savings = {}
                    for [[p1, p2], sv] in savings_list:
                        savings[(p1, p2)] = sv

                    for pruning_density in pruning_density_list:
                        for num_iterations in num_iterations_list:
                            total_time_in_ms = 0
                            min_costs = inf
                            result_list = []
                            for j in samples_list:
                                data_path = data_path_prefix + '/' + str(num_queries) + '_queries/' + str(num_plans_per_query) + '_ppq/density_' + str(density) + '/cost_scaling_' + str(cost_scaling) + '/problem_' + str(p) + '/' + 'pruning_density_' + str(pruning_density) + '/' + str(num_runs) + '_runs/' + str(num_iterations) + '_iterations/sample_' + str(j)
                                if not os.path.exists(data_path):
                                    continue
                                result = load_data(data_path, "response.txt")
                                total_time_in_ms = total_time_in_ms + result[1]
                                bitstrings = []

                                for solution in result[0]:
                                    for i in range(int(solution[1])):
                                        bitstrings.append(solution[0])

                                min_sample_costs = inf
                                best_sample_config = None
                                for bitstring in bitstrings:
                                    active_plans = np.argwhere(np.array(bitstring) == 1)
                                    active_plans = [int(x) for x in active_plans]
                                    costs = evaluate_mqo_solution(active_plans, plan_costs, num_plans_per_query, savings)
                                    if costs < min_sample_costs:
                                        best_sample_config = active_plans
                                        min_sample_costs = costs
                                if min_sample_costs < min_costs:
                                    min_costs = min_sample_costs
                                    result_list.append({"time_in_ms":total_time_in_ms, "costs": min_sample_costs, "plan_selection": best_sample_config})


                            result_path = result_path_prefix + '/' + str(num_queries) + '_queries/' + str(num_plans_per_query) + '_ppq/density_' + str(density) + '/cost_scaling_' + str(cost_scaling) + '/problem_' + str(p)
                            save_data(result_list, result_path, 'simulated_annealing_' + 'pr_' + str(pruning_density) + '_it_' + str(num_iterations) + '.json')    


