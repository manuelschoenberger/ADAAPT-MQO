#!/usr/bin/env python
# coding: utf-8

# In[1]:


import numpy as np
import itertools
import unittest

import json
import os
import pickle
import pathlib 
import csv

from qiskit.compiler import transpile
from qiskit import(QuantumCircuit, execute, Aer, BasicAer)
from qiskit.visualization import plot_histogram
from qiskit_optimization import QuadraticProgram
from qiskit_optimization.algorithms import GroverOptimizer
from docplex.mp.model import Model
from qiskit.utils import algorithm_globals, QuantumInstance
from qiskit.algorithms import NumPyMinimumEigensolver
import qiskit.algorithms
from qiskit_optimization.algorithms import MinimumEigenOptimizer, RecursiveMinimumEigenOptimizer
from qiskit import IBMQ
from qiskit_optimization.translators import from_docplex_mp
from qiskit.algorithms.optimizers import AQGD
from qiskit.circuit.library import EfficientSU2

import dimod
from dimod.reference.samplers import ExactSolver
from neal.sampler import SimulatedAnnealingSampler

from dadk.BinPol import BinPol
from dadk.QUBOSolverCPU import *


# In[2]:


def calculate_wl(costs, epsilon):
    return max(costs)+epsilon

def calculate_wm(num_plans, savings, wl):
    if not savings:
        return wl
    max_savings_for_plan = np.zeros(num_plans)
    for [[i,j],s] in savings:
        max_savings_for_plan[i] = max_savings_for_plan[i] + s
        max_savings_for_plan[j] = max_savings_for_plan[j] + s
    return wl + max(max_savings_for_plan)


# In[ ]:


def load_data(path, filename):
    file_path = os.path.abspath(path + "/" + filename)
    if os.path.exists(file_path):
        with open(file_path) as file:
            return json.load(file)

# Loads and returns the mqo collections from the queries, costs and savings files from the provided path
def load_MQO_instance_from_disc(mqo_path):

    queries = load_data(mqo_path, "queries.txt")
    costs = load_data(mqo_path, "costs.txt")
    savings = load_data(mqo_path, "savings.txt")
    
    return queries, costs, savings


# In[ ]:


def apply_pruning_old(plan_costs, savings, pruning_density, queries):

    query_for_plan = {}
    for (query,plans) in queries.items():
        for plan in plans:
            query_for_plan[plan] = query
    num_savings = len(savings)
    num_pruned_savings = int(num_savings * (1 - pruning_density))
    savings_values = []
    for i in range(num_savings):
        savings_values.append(savings[i][1])
    pruned_indices = np.argpartition(savings_values, num_pruned_savings)[:num_pruned_savings]

    new_plan_costs = plan_costs.copy()
    for pruned_index in pruned_indices:
        savings_value = savings_values[pruned_index]
        plan1 = savings[pruned_index][0][0]
        plan2 = savings[pruned_index][0][1]

        plan1_query_ratio = 1/len(queries[query_for_plan[plan1]])
        plan2_query_ratio = 1/len(queries[query_for_plan[plan2]])
        new_plan_costs[plan1] = new_plan_costs[plan1] - savings_value*0.5*plan2_query_ratio
        new_plan_costs[plan2] = new_plan_costs[plan2] - savings_value*0.5*plan1_query_ratio
        
    new_savings = np.delete(np.array(savings.copy()), pruned_indices, axis=0).tolist()
    return new_plan_costs, new_savings
    
def apply_pruning(savings, pruning_density, queries):
    import time

    num_savings = len(savings)
    num_pruned_savings = int(num_savings * (1 - pruning_density))
    savings_values = []
    savings_values_start = time.time()
    for i in range(num_savings):
        savings_values.append(savings[i][1])
    pruned_indices_start = time.time()
    pruned_indices = np.argpartition(savings_values, num_pruned_savings)[:num_pruned_savings]
    new_savings_start = time.time()
    
    pruned_indices = set(pruned_indices)
    new_savings = [x for i, x in enumerate(savings) if i not in pruned_indices]
    return new_savings

def generate_QUBO_matrix(queries, costs, savings, pruning_density=None):
    num_plans = len(costs)
    qubo_matrix = np.zeros((num_plans, num_plans))
    
    if pruning_density != None and pruning_density < 1:
        savings = apply_pruning(savings, pruning_density, queries)
        
        
    savings_matrix = np.zeros((num_plans, num_plans)).tolist()
    for [[p1, p2], sv] in savings:
        savings_matrix[p1][p2] = sv
        savings_matrix[p2][p1] = sv
        
    epsilon = 0.25
    
    wl= calculate_wl(costs, epsilon)
    wm= calculate_wm(num_plans, savings, wl)
    
    query_for_plan = {}
    for (q, plans) in queries.items():
        for plan in plans:
            query_for_plan[int(plan)] = int(q)
    
    for i in range(num_plans):
        for j in range(num_plans):
            if i == j:
                qubo_matrix[i][i] = costs[i]-wl
            elif j > i:
                if query_for_plan[i] == query_for_plan[j]:
                    qubo_matrix[i][j] = wm
                    qubo_matrix[j][i] = wm
                qubo_matrix[i][j] = qubo_matrix[i][j] - savings_matrix[i][j]
                qubo_matrix[j][i] = qubo_matrix[j][i] - savings_matrix[j][i]
    
    return qubo_matrix
                    

## IBM Q QUBO Generation
def generate_IBMQ_QUBO(queries, costs, savings, pruning_density=None, penalty_scaling=1):
    model = Model('docplex_model')
    
    if pruning_density != None or pruning_density < 1:
        savings = apply_pruning(savings, pruning_density, queries)
   

    num_plans = len(costs)
    v = model.binary_var_list(len(costs))
    epsilon = 0.25
    
    wl= calculate_wl(costs, epsilon)
    wm= calculate_wm(num_plans, savings, wl)
    
    El = model.sum(-1*(wl-costs[i])*v[i] for i in range(0, len(costs)))
    Em = model.sum(model.sum(wm*v[i]*v[j] for (i,j) in itertools.combinations(queries[k], 2)) 
                   for k in queries.keys())
    Es = model.sum(-s*v[i]*v[j] for ((i,j), s) in savings)
    
    model.minimize((El + Em + Es))

    qubo = from_docplex_mp(model)
    
    return qubo

def generate_DWave_QUBO(queries, costs, savings, pruning_density=None, penalty_scaling=1):
    ibmq_qubo = generate_IBMQ_QUBO(queries, costs, savings, pruning_density=pruning_density, penalty_scaling=penalty_scaling)
    dwave_qubo = dimod.as_bqm(ibmq_qubo.objective.linear.to_array(), ibmq_qubo.objective.quadratic.to_array(), ibmq_qubo.objective.constant, dimod.BINARY)
    return dwave_qubo

def generate_Fujitsu_QUBO(queries, costs, savings, pruning_density=None, penalty_scaling=1):
    qubo_matrix = generate_QUBO_matrix(queries, costs, savings, pruning_density=pruning_density)
    
    fujitsu_qubo = BinPol(qubo_matrix_array=qubo_matrix)
    return fujitsu_qubo