package mqo_chimera;

import com.fasterxml.jackson.databind.ObjectMapper;
import ilog.concert.IloException;
import mqo_chimera.benchmark.BenchmarkConfiguration;
import mqo_chimera.benchmark.TestcaseClass;
import mqo_chimera.mapping.ChimeraMqoMapping;
import mqo_chimera.solver.Solver;
import mqo_chimera.solver.climbing.HillClimber;
import mqo_chimera.solver.cplex.LinearSolver;
import mqo_chimera.solver.genetic.GeneticSolver;
import mqo_chimera.testcases.ChimeraFactory;
import mqo_chimera.testcases.ChimeraMqoProblem;
import mqo_chimera.testcases.MqoSolution;
import org.jgap.Gene;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.sql.Array;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;
import java.util.stream.LongStream;
import java.util.zip.GZIPInputStream;


public class App 
{

    enum Baseline {
        ilp,
        genetic,
        hillClimbing
    }

    public static ChimeraMqoProblem getMQOProblem(int num_queries, int num_plans_per_query, String problemPath) {
        ObjectMapper objectMapper = new ObjectMapper();
        Map<String, List<Integer>> queries = new HashMap<>();
        List<Integer> planCosts = new ArrayList<>();
        List<List<Object>> savingsList = new ArrayList<>();
        try {
            // Expected plan costs format: planCosts[i]: costs for plan with index i
            // 0 <= i <= num_plans_per_query-1: plans for query 0
            // num_plans_per_query <= i <= 2*num_plans_per_query-1: plans for query 1...
            //planCosts = objectMapper.readValue(new File(problemPath + "/plan_costs.txt"), List.class);
            planCosts = objectMapper.readValue(new GZIPInputStream(new FileInputStream(problemPath + "/plan_costs.txt")), List.class);

            // Expected savings format: [[[plan1_index, plan2_index], savings_val1], [[plan1_index, plan2_index], savings_val2], ...]
            //savingsList = objectMapper.readValue(new File(problemPath + "/savings_list.txt"), List.class);
            savingsList = objectMapper.readValue(new GZIPInputStream(new FileInputStream(problemPath + "/savings_list.txt")), List.class);

        } catch (IOException e) {
            throw new RuntimeException(e);
        }
        ChimeraMqoProblem mqoProblem = new ChimeraMqoProblem(num_queries, num_plans_per_query, false);
        for (int j = 0; j < num_queries; j++) {
            for (int l = 0; l < num_plans_per_query; l++) {
                mqoProblem.planCost[j][l] = planCosts.get(j*num_plans_per_query+l);
            }
        }
        
        Instant start = Instant.now();
        int counter = 0;
        for (List<Object> savings: savingsList) {
            counter = counter + 1;
            long startTime = System.nanoTime();
            List<Integer> planList = (List<Integer>)savings.get(0);
            int savingsVal = (int)savings.get(1);
            int q1 = planList.get(0) / num_plans_per_query;
            int q2 = planList.get(1) / num_plans_per_query;
            int p1 = planList.get(0) % num_plans_per_query;
            int p2 = planList.get(1) % num_plans_per_query;

            mqoProblem.addInterference(q1, p1, q2, p2, -1*savingsVal);
            long stopTime = System.nanoTime();
            Instant end = Instant.now();
        }
        return mqoProblem;
    }


    public static void solveMQOProblem(ChimeraMqoProblem mqoProblem, Baseline baseline, int geneticPopulationSize, Path resultDir, String filename) {
        MqoSolution solution = null;
        Solver solver = null;
        switch(baseline) {
            case genetic:
                System.out.println("Genetic Solver");
                solver = new GeneticSolver(geneticPopulationSize);
                break;
            case hillClimbing:
                System.out.println("Hill Climbing Solver");
                solver = new HillClimber();
                break;
            case ilp:
                try {
                    System.out.println("ILP Solver");
                    solver = new LinearSolver();
                } catch (IloException e) {
                    System.out.println("Error: ILP Solver could not be instantiated.");
                }
                break;
        }
        if (solver != null) {
            try {
                solution = solver.solve(mqoProblem);
            } catch (Exception e) {
                System.out.println(e.getMessage());
                System.out.println("Error: Exception during solution process.");
            }
        }

        Map<String, Object> solutionMap = new HashMap();
        System.out.println(solution.planSelections);
        int[] planSelection = null;
        if (solution != null) {
            planSelection = solution.planSelections;
        }
        if (planSelection == null) {
            // No solution was found -> prepare empty solution for export
            planSelection = new int[]{};
            solutionMap.put("plan_selection", planSelection);
            solutionMap.put("costs", "n/a");
            solutionMap.put("cost_evolution", "n/a");
        } else {
            // Prepare solution for export
            solutionMap.put("plan_selection", planSelection);
            solutionMap.put("costs", solution.executionCost);
            double[] timeCosts = solver.lastRunCheckpointCost;
            Map<Long, Double> costsForTimes = new TreeMap<>();
            for (int i = 0; i < timeCosts.length; i++) {
                long time = BenchmarkConfiguration.benchmarkTimes[i];
                costsForTimes.put(time, timeCosts[i]);
            }
            solutionMap.put("cost_evolution", costsForTimes);
        }

        try {
            ObjectMapper objectMapper = new ObjectMapper();
            Files.createDirectories(resultDir);
            objectMapper.writeValue(new File(resultDir + "/" + filename), solutionMap);

        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    public static void runExperiments(List<Integer> num_queries_list, List<Integer> num_plans_per_query_list, List<Double> density_list, List<Integer> cost_scaling_list, List<Integer> problems, List<Baseline> baselines, List<Integer> geneticPopulationSizes) {

            for (Integer num_queries: num_queries_list) {
                for (Integer num_plans_per_query: num_plans_per_query_list) {
                    for (Double density: density_list) {
                        for (Integer cost_scaling: cost_scaling_list) {
                            for (Integer problem: problems) {
                                String problemPath = "ExperimentalAnalysis/RefinedExperiments/Problems/" + num_queries + "_queries/" + num_plans_per_query + "_ppq/density_" + density + "/cost_scaling_" + cost_scaling + "/problem_" + problem;
                                //String problemPath = "ExperimentalAnalysis/CostTesting/ProblemsFinal/" + num_queries + "_queries/" + num_plans_per_query + "_ppq/density_" + density + "/cost_scaling_" + cost_scaling + "/problem_" + problem;

                                String resultDirString = "ExperimentalAnalysis/RefinedExperiments/BaselineResultsILP/" + num_queries + "_queries/" + num_plans_per_query + "_ppq/density_" + density + "/cost_scaling_" + cost_scaling + "/problem_" + problem;
                                //String resultDirString = "ExperimentalAnalysis/CostTesting/BaselineResultsFinal/" + num_queries + "_queries/" + num_plans_per_query + "_ppq/density_" + density + "/cost_scaling_" + cost_scaling + "/problem_" + problem;

                                File problemPathFile = new File(problemPath);
                                if(!problemPathFile.exists()) {
                                    continue;
                                }

                                System.out.println(resultDirString);
                                Path resultDir = Paths.get(resultDirString);

                                ChimeraMqoProblem mqoProblem = null;
                                if (baselines.contains(Baseline.hillClimbing)) {
                                    File f = new File(resultDir + "/hill_climbing.json");
                                    if(!f.exists() || f.isDirectory()) {
                                        if (mqoProblem == null) {
                                            mqoProblem = getMQOProblem(num_queries, num_plans_per_query, problemPath);
                                        }
                                        solveMQOProblem(mqoProblem, Baseline.hillClimbing, 0, resultDir, "hill_climbing.json");
                                    }
                                }
                                if (baselines.contains(Baseline.ilp)) {
                                    File f = new File(resultDir + "/ilp.json");
                                    if(!f.exists() || f.isDirectory()) {
                                        if (mqoProblem == null) {
                                            mqoProblem = getMQOProblem(num_queries, num_plans_per_query, problemPath);
                                        }
                                        solveMQOProblem(mqoProblem, Baseline.ilp, 0, resultDir, "ilp.json");
                                    }
                                }
                                if (baselines.contains(Baseline.genetic)) {
                                    for (Integer populationSize: geneticPopulationSizes) {
                                        File f = new File(resultDir + "/genetic_" + populationSize + ".json");
                                        if(!f.exists() || f.isDirectory()) {
                                            if (mqoProblem == null) {
                                                mqoProblem = getMQOProblem(num_queries, num_plans_per_query, problemPath);
                                            }
                                            solveMQOProblem(mqoProblem, Baseline.genetic, populationSize, resultDir, "genetic_" + populationSize + ".json");

                                        }
                                    }

                                }


                            }
                        }

                    }

                }

            }
    }

    public static int[] transformPlanSelectionToBaselineFormat(int[] rawPlanSelection, int numPlansPerQuery) {
        int[] planSelection = new int[rawPlanSelection.length];
        for (int i = 0; i < rawPlanSelection.length; i++) {
            planSelection[i] = rawPlanSelection[i] % numPlansPerQuery;
        }
        return planSelection;
    }

    public static double getCostsForMQOProblemAndPlanSelection(int num_queries, int num_plans_per_query, double density, int cost_scaling, int problem, int[] rawPlanSelection) {
        String problemPath = "ExperimentalAnalysis/RefinedExperiments/Problems/" + num_queries + "_queries/" + num_plans_per_query + "_ppq/density_" + density + "/cost_scaling_" + cost_scaling + "/problem_" + problem;
        ChimeraMqoProblem mqoProblem = getMQOProblem(num_queries, num_plans_per_query, problemPath);
        int[] planSelection = transformPlanSelectionToBaselineFormat(rawPlanSelection, num_plans_per_query);
        System.out.println(Arrays.toString(planSelection));
        MqoSolution solution = new MqoSolution(mqoProblem, planSelection);
        return solution.executionCost;
    }


    public static void main( String[] args )
    {
        
    }
}
