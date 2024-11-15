# ADAAPT-MQO: Adaptive Digital Annealing-Approximated Multiple Query Optimisation

This repository contains code and data artifacts for the Adaptive Digital Annealing-Approximated Multiple Query Optimisation (ADAAPT-MQO) method.

## Project Structure

Code to conduct experiments for our MQO-QUBO methods, including both local simulated annealing as well as the Fujitsu Digital Annealer [1] approach, is contained in SimulatedAnnealing.py and DigitalAnnealing.py respectively. Scripts/MQOProblemGenerator.py contains code for generating MQO problems in accordance to our synthetic benchmark. All generated problems can be found in ExperimentalAnalysis/Problems, in compressed form.

Scripts/QUBOGenerator.py constructs MQO-QUBO encodings based on our ADAAPT method, allowing their deployment on the Fujitsu Digital Annealer [1]. All annealing results, including those collected on the Fujitsu DA, for all problems can be found in ExperimentalAnalysis/Data.

Finally, baseline MQO implementations, including hill climbing [2], integer linear programming [3] and a genetic algorithm [4], based on code by Trummer [5] implemented in Java, can be found in the Baseline directory. We optimised the implementations to increase baseline performance.

## References

[1] Fujitsu Limited. 2023. Fujitsu Digital Annealer - solving large-scale combinatorial optimization problems instantly. https://www.fujitsu.com/emeia/services/business-services/digital-annealer/what-is-digital-annealer/

[2] Tansel Dokeroglu, Murat Ali Bayir, and Ahmet Cosar. 2015. Robust Heuristic Algorithms for Exploiting the Common Tasks of Relational Cloud Database Queries. Appl. Soft Comput. 30, C (may 2015), 72–82. https://doi.org/10.1016/j.asoc.2015.01.026

[3] Tansel Dokeroglu, Murat Ali Bayır, and Ahmet Cosar. 2014. Integer Linear Programming Solution for the Multiple Query Optimization Problem. In Information Sciences and Systems 2014, Tadeusz Czachórski, Erol Gelenbe, and Ricardo Lent (Eds.). Springer International Publishing, Cham, 51–60. https://doi.org/10.1007/978-3-319-09465-6_6

[4] Murat Ali Bayir, Ismail H. Toroslu, and Ahmet Cosar. 2007. Genetic Algorithm for the Multiple-Query Optimization Problem. IEEE Transactions on Systems, Man, and Cybernetics, Part C (Applications and Reviews) 37, 1 (2007), 147–153. https://doi.org/10.1109/TSMCC.2006.876060

[5] Immanuel Trummer. 2022. quantumdb. https://github.com/itrummer/quantumdb
