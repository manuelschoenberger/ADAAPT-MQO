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
from dadk.QUBOSolverDAv2 import QUBOSolverDAv2
from dadk.QUBOSolverCPU import *
import Scripts.DataExport as DataExport
import Scripts.DataUtil as DataUtil
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

def save_data(data, path, filename, override=True):
    print(path + '/' + filename)
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


# In[3]:


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


# In[4]:


def solve_problem(fujitsu_qubo, da_algorithm='annealing', number_runs=100, number_iterations=1000000, test_with_local_solver=False):
    if test_with_local_solver:
        solver = QUBOSolverCPU(number_runs=number_runs)
    else:
        if da_algorithm == 'annealing':
            solver = QUBOSolverDAv2(optimization_method=da_algorithm, timeout=60, number_iterations=number_iterations, number_runs=number_runs, access_profile_file='annealer.prf', use_access_profile=True)
        else:
            solver = QUBOSolverDAv2(optimization_method=da_algorithm, timeout=60, number_iterations=number_iterations, number_replicas=number_runs, access_profile_file='annealer.prf', use_access_profile=True)

    #solution_list = solver.minimize(fujitsu_qubo)        
    while True:
        try:
            solution_list = solver.minimize(fujitsu_qubo)
            break
        except:
            print("Library error. Repeating request")

    execution_time = solution_list.execution_time.total_seconds()
    anneal_time = solution_list.anneal_time.total_seconds()
    solutions = solution_list.solutions
    return solutions, execution_time, anneal_time

def parse_solutions_for_serialisation(raw_solutions):
    response = []
    for raw_solution in raw_solutions:
        solution = [raw_solution.configuration, int(raw_solution.frequency), float(raw_solution.energy)]
        response.append(solution)
    return response


# In[5]:


def get_algorithm_string(algorithm):
    if algorithm == 'digital_annealing':
        return 'annealing'
    elif algorithm == 'parallel_tempering':
        return 'parallel_tempering'
    return ""

def conduct_experiment(num_queries_list, num_plans_per_query_list, density_list, problems, pruning_density_list, algorithms, num_runs, num_iterations_list, samples, problem_path_prefix, result_path_prefix):
    for num_queries in num_queries_list:
        for num_plans_per_query in num_plans_per_query_list:
            for (density, cost_scaling) in density_list:
                #for cost_scaling in cost_scaling_list:
                for i in problems:
                    problem_path = problem_path_prefix + '/' + str(num_queries) + '_queries/' + str(num_plans_per_query) + '_ppq/density_' + str(density) + '/cost_scaling_' + str(cost_scaling) + '/problem_' + str(i)
                    if not os.path.exists(problem_path):
                        continue
                    queries = DataUtil.load_compressed_data(problem_path, 'queries.txt')
                    plan_costs = DataUtil.load_compressed_data(problem_path, 'plan_costs.txt') 
                    savings = DataUtil.load_compressed_data(problem_path, 'savings_list.txt')

                    for pruning_density in pruning_density_list:
                        qubo = MQOQuboGenerator.generate_Fujitsu_QUBO(queries, plan_costs, savings, pruning_density)
                        for algorithm in algorithms:
                            for num_iterations in num_iterations_list:
                                for j in samples:
                                    result_path = result_path_prefix + '/' + algorithm + '/' + str(num_queries) + '_queries/' + str(num_plans_per_query) + '_ppq/density_' + str(density) + '/cost_scaling_' + str(cost_scaling) + '/problem_' + str(i) + '/' + 'pruning_density_' + str(pruning_density) + '/' + str(num_runs) + '_runs/' + str(num_iterations) + '_iterations/sample_' + str(j)
                                    raw_solutions, execution_time, anneal_time = solve_problem(qubo, da_algorithm=get_algorithm_string(algorithm), number_runs=num_runs, number_iterations=num_iterations, test_with_local_solver=False)
                                    solutions = parse_solutions_for_serialisation(raw_solutions)
                                    DataUtil.compress_and_save_data([solutions, float(execution_time), float(anneal_time)], result_path, "response.txt")
                                
def export_results(num_queries_list, num_plans_per_query_list, density_list, problems_list, pruning_density_list, algorithms, samples_list, num_runs, num_iterations_list, problem_path_prefix, data_path_prefix, result_path_prefix):
    for num_queries in num_queries_list:
        for num_plans_per_query in num_plans_per_query_list:
            for (density, cost_scaling) in density_list:
                #for cost_scaling in cost_scaling_list:
                for p in problems_list:
                    problem_path = problem_path_prefix + '/' + str(num_queries) + '_queries/' + str(num_plans_per_query) + '_ppq/density_' + str(density) + '/cost_scaling_' + str(cost_scaling) + '/problem_' + str(p)

                    if not os.path.exists(problem_path):
                        continue
                        
                    queries = DataUtil.load_compressed_data(problem_path, 'queries.txt')
                    plan_costs = DataUtil.load_compressed_data(problem_path, 'plan_costs.txt') 
                    savings_list = DataUtil.load_compressed_data(problem_path, 'savings_list.txt')
                    savings = {}
                    for [[p1, p2], sv] in savings_list:
                        savings[(p1, p2)] = sv

                    for pruning_density in pruning_density_list:
                        for algorithm in algorithms:
                            for num_iterations in num_iterations_list:
                                total_time_in_ms = 0
                                min_costs = inf
                                result_list = []
                                for j in samples_list:
                                    data_path = data_path_prefix + '/' + algorithm + '/' + str(num_queries) + '_queries/' + str(num_plans_per_query) + '_ppq/density_' + str(density) + '/cost_scaling_' + str(cost_scaling) + '/problem_' + str(p) + '/' + 'pruning_density_' + str(pruning_density) + '/' + str(num_runs) + '_runs/' + str(num_iterations) + '_iterations/sample_' + str(j)
                                    if not os.path.exists(data_path):
                                        continue
                                    #result = DataUtil.load_compressed_data(data_path, "response.txt")
                                    result = DataUtil.load_compressed_data(data_path, "response.txt")

                                    total_time_in_ms = total_time_in_ms + result[1]*1000
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
                                        if costs == False:
                                            continue
                                        if costs < min_sample_costs:
                                            best_sample_config = active_plans
                                            min_sample_costs = costs
                                    if min_sample_costs < min_costs:
                                        min_costs = min_sample_costs
                                        result_list.append({"time_in_ms":total_time_in_ms, "costs": min_sample_costs, "plan_selection": best_sample_config})


                                result_path = result_path_prefix + '/' + str(num_queries) + '_queries/' + str(num_plans_per_query) + '_ppq/density_' + str(density) + '/cost_scaling_' + str(cost_scaling) + '/problem_' + str(p)
                                save_data(result_list, result_path, algorithm + '_pr_' + str(pruning_density) + '_it_' + str(num_iterations) + '.json')

def export_adaapt_results(num_queries_list, num_plans_per_query_list, density_list, problems_list, samples_list, num_runs, num_iterations_list, problem_path_prefix, adaapt_config_path_prefix, data_path_prefix, result_path_prefix):
    for num_queries in num_queries_list:
        for num_plans_per_query in num_plans_per_query_list:
            for (density, cost_scaling) in density_list:
                #for cost_scaling in cost_scaling_list:
                for p in problems_list:
                    problem_path = problem_path_prefix + '/' + str(num_queries) + '_queries/' + str(num_plans_per_query) + '_ppq/density_' + str(density) + '/cost_scaling_' + str(cost_scaling) + '/problem_' + str(p)
                    adaapt_config_path = adaapt_config_path_prefix + '/' + str(num_queries) + '_queries/' + str(num_plans_per_query) + '_ppq/density_' + str(density)
                    
                    if not os.path.exists(problem_path) or not os.path.exists(adaapt_config_path):
                        continue
                        
                    queries = DataUtil.load_compressed_data(problem_path, 'queries.txt')
                    plan_costs = DataUtil.load_compressed_data(problem_path, 'plan_costs.txt') 
                    savings_list = DataUtil.load_compressed_data(problem_path, 'savings_list.txt')
                    adaapt_config = DataUtil.load_data(adaapt_config_path, 'adaapt_config.txt')
                    
                    savings = {}
                    for [[p1, p2], sv] in savings_list:
                        savings[(p1, p2)] = sv

                    for num_iterations in num_iterations_list:
                        min_costs = inf
                        result_list = []
                        
                        adaapt_index = 0
                        while adaapt_index < len(adaapt_config):
                            [current_timeout_in_ms, pruning_density] = adaapt_config[adaapt_index]
                            total_time_in_ms = 0
                            for j in samples_list:
                                data_path = data_path_prefix + '/digital_annealing/' + str(num_queries) + '_queries/' + str(num_plans_per_query) + '_ppq/density_' + str(density) + '/cost_scaling_' + str(cost_scaling) + '/problem_' + str(p) + '/' + 'pruning_density_' + str(pruning_density) + '/' + str(num_runs) + '_runs/' + str(num_iterations) + '_iterations/sample_' + str(j)
                                if not os.path.exists(data_path):
                                    continue
                                #result = DataUtil.load_compressed_data(data_path, "response.txt")
                                result = DataUtil.load_compressed_data(data_path, "response.txt")

                                total_time_in_ms = total_time_in_ms + result[1]*1000
                                if total_time_in_ms > current_timeout_in_ms:
                                    break
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
                                    if costs == False:
                                        continue
                                    if costs < min_sample_costs:
                                        best_sample_config = active_plans
                                        min_sample_costs = costs
                                if min_sample_costs < min_costs:
                                    min_costs = min_sample_costs
                                    result_list.append({"time_in_ms":current_timeout_in_ms, "costs": min_sample_costs, "plan_selection": best_sample_config})
                            adaapt_index = adaapt_index + 1

                        result_path = result_path_prefix + '/' + str(num_queries) + '_queries/' + str(num_plans_per_query) + '_ppq/density_' + str(density) + '/cost_scaling_' + str(cost_scaling) + '/problem_' + str(p)
                        save_data(result_list, result_path, 'ADAAPT' + '_it_' + str(num_iterations) + '.json')
                                                            


