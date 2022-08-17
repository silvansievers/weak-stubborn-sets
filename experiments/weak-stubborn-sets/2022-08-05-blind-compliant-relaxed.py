#! /usr/bin/env python3

from collections import defaultdict
from itertools import chain, combinations
import os
from pathlib import Path
import subprocess

from lab.environments import LocalEnvironment, BaselSlurmEnvironment
from lab.reports import Attribute, arithmetic_mean, geometric_mean

from downward.reports.compare import ComparativeReport
from downward.reports.scatter import ScatterPlotReport

import common_setup
from common_setup import IssueConfig, IssueExperiment

DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_NAME = os.path.splitext(os.path.basename(__file__))[0]
BENCHMARKS_DIR = os.environ['DOWNWARD_BENCHMARKS']
OLD_REV='57539f317b9e0b63f63a2d944715409ef10a4301'
REVISION='a663d67a8003639b856d495a4a17233a337975ad'
REVISIONS = [REVISION]
HEURISTICS = [
    ("blind", "blind()"),
]

SIMPLE_CONFIGS = list(chain.from_iterable(
    (
    IssueConfig(
        "{nick}-simple-{ss_type}-min{min_pruning}".format(**locals()),
        ["--search", "astar({heuristic},pruning=limited_pruning(stubborn_sets_simple(stubborn_set_type={ss_type},use_mutex_interference=false),min_required_pruning_ratio={min_pruning}),verbosity=silent)".format(**locals())], driver_options=['--search-time-limit', '5m']),
    )
    for nick, heuristic in HEURISTICS
    for ss_type in ["strong", "weak", "compliant", "compliant_relaxed"]
    for min_pruning in ["0.0"] # "0.2"
))

CONFIGS = SIMPLE_CONFIGS

SUITE = common_setup.DEFAULT_OPTIMAL_SUITE
ENVIRONMENT = BaselSlurmEnvironment(
    email="silvan.sievers@unibas.ch",
    partition="infai_2",
    export=[],
    # paths obtained via:
    # module purge
    # module -q load Python/3.7.4-GCCcore-8.3.0
    # module -q load CMake/3.15.3-GCCcore-8.3.0
    # module -q load GCC/8.3.0
    # echo $PATH
    # echo $LD_LIBRARY_PATH
    setup='export PATH=/scicore/soft/apps/CMake/3.15.3-GCCcore-8.3.0/bin:/scicore/soft/apps/cURL/7.66.0-GCCcore-8.3.0/bin:/scicore/soft/apps/Python/3.7.4-GCCcore-8.3.0/bin:/scicore/soft/apps/XZ/5.2.4-GCCcore-8.3.0/bin:/scicore/soft/apps/SQLite/3.29.0-GCCcore-8.3.0/bin:/scicore/soft/apps/Tcl/8.6.9-GCCcore-8.3.0/bin:/scicore/soft/apps/ncurses/6.1-GCCcore-8.3.0/bin:/scicore/soft/apps/bzip2/1.0.8-GCCcore-8.3.0/bin:/scicore/soft/apps/binutils/2.32-GCCcore-8.3.0/bin:/scicore/soft/apps/GCCcore/8.3.0/bin:/infai/sieverss/repos/bin:/infai/sieverss/local:/export/soft/lua_lmod/centos7/lmod/lmod/libexec:/usr/local/bin:/usr/bin:/usr/local/sbin:/usr/sbin:$PATH\nexport LD_LIBRARY_PATH=/scicore/soft/apps/cURL/7.66.0-GCCcore-8.3.0/lib:/scicore/soft/apps/Python/3.7.4-GCCcore-8.3.0/lib:/scicore/soft/apps/libffi/3.2.1-GCCcore-8.3.0/lib64:/scicore/soft/apps/libffi/3.2.1-GCCcore-8.3.0/lib:/scicore/soft/apps/GMP/6.1.2-GCCcore-8.3.0/lib:/scicore/soft/apps/XZ/5.2.4-GCCcore-8.3.0/lib:/scicore/soft/apps/SQLite/3.29.0-GCCcore-8.3.0/lib:/scicore/soft/apps/Tcl/8.6.9-GCCcore-8.3.0/lib:/scicore/soft/apps/libreadline/8.0-GCCcore-8.3.0/lib:/scicore/soft/apps/ncurses/6.1-GCCcore-8.3.0/lib:/scicore/soft/apps/bzip2/1.0.8-GCCcore-8.3.0/lib:/scicore/soft/apps/binutils/2.32-GCCcore-8.3.0/lib:/scicore/soft/apps/zlib/1.2.11-GCCcore-8.3.0/lib:/scicore/soft/apps/GCCcore/8.3.0/lib64:/scicore/soft/apps/GCCcore/8.3.0/lib')

if common_setup.is_test_run():
    SUITE = IssueExperiment.DEFAULT_TEST_SUITE
    ENVIRONMENT = LocalEnvironment(processes=4)

exp = IssueExperiment(
    revisions=REVISIONS,
    configs=CONFIGS,
    environment=ENVIRONMENT,
)
exp.add_suite(BENCHMARKS_DIR, SUITE)

exp.add_parser(exp.EXITCODE_PARSER)
exp.add_parser(exp.TRANSLATOR_PARSER)
exp.add_parser(exp.SINGLE_SEARCH_PARSER)
exp.add_parser(exp.PLANNER_PARSER)
exp.add_parser("ss-parser.py")

exp.add_step('build', exp.build)
exp.add_step('start', exp.start_runs)
exp.add_fetcher(name='fetch')

ss_successors_unpruned = Attribute("ss_successors_unpruned", absolute=True, min_wins=True)
ss_successors_pruned = Attribute("ss_successors_pruned", absolute=True, min_wins=True)
ss_pruning_ratio = Attribute("ss_pruning_ratio", absolute=False, min_wins=False)
ss_pruning_time = Attribute("ss_pruning_time", absolute=False, min_wins=True, function=geometric_mean)

extra_attributes = [
    ss_successors_unpruned,
    ss_successors_pruned,
    ss_pruning_ratio,
    ss_pruning_time,
]
attributes = list(exp.DEFAULT_TABLE_ATTRIBUTES)
attributes.extend(extra_attributes)

exp.add_absolute_report_step(
    filter_algorithm=[f"{REVISION}-{config.nick}" for config in CONFIGS],
    attributes=attributes,
)

report_name=f'{exp.name}-compare'
report_file=Path(exp.eval_dir) / f'{report_name}.html'
exp.add_report(
    ComparativeReport(
        attributes=attributes,
        algorithm_pairs=[
            (f'{REVISION}-{pair[0].nick}', f'{REVISION}-{pair[1].nick}') for pair in combinations(SIMPLE_CONFIGS, 2)
        ],
    ),
    name=report_name,
    outfile=report_file,
)
exp.add_step(f'publish-{report_name}', subprocess.call, ['publish', report_file])

unsolvable = ['miconic-fulladl:f21-3.pddl', 'miconic-fulladl:f30-2.pddl', 'mystery:prob04.pddl', 'mystery:prob05.pddl', 'mystery:prob07.pddl', 'mystery:prob08.pddl', 'mystery:prob12.pddl', 'mystery:prob16.pddl', 'mystery:prob18.pddl', 'mystery:prob21.pddl', 'mystery:prob22.pddl', 'mystery:prob23.pddl', 'mystery:prob24.pddl']

def filter_unsolvable_tasks(run):
    return "{}:{}".format(run['domain'], run['problem']) not in unsolvable

domain_groups_optimal = {
'agricola-opt18-strips': 'agricola',
'airport': 'airport', # identity
'assembly': 'assembly', # identity
'barman-opt11-strips': 'barman',
'barman-opt14-strips': 'barman',
'blocks': 'blocks', # identity
'caldera-opt18-adl': 'caldera',
'caldera-split-opt18-adl': 'caldera-split',
'cavediving-14-adl': 'cavediving',
'childsnack-opt14-strips': 'childsnack',
'citycar-opt14-adl': 'citycar',
'data-network-opt18-strips': 'data-network',
'depot': 'depot', # identity
'driverlog': 'driverlog', # identity
'elevators-opt08-strips': 'elevators',
'elevators-opt11-strips': 'elevators',
'floortile-opt11-strips': 'floortile',
'floortile-opt14-strips': 'floortile',
'freecell': 'freecell', # identity
'ged-opt14-strips': 'ged',
'grid': 'grid', # identity
'gripper': 'gripper', # identity
'hiking-opt14-strips': 'hiking',
'logistics00': 'logistics',
'logistics98': 'logistics',
'maintenance-opt14-adl': 'maintenance',
'miconic': 'miconic', # identity
'miconic-fulladl': 'miconic',
'miconic-simpleadl': 'miconic',
'movie': 'movie', # identity
'mprime': 'mprime', # identity
'mystery': 'mystery', # identity
'nomystery-opt11-strips': 'nomystery',
'nurikabe-opt18-adl': 'nurikabe',
'openstacks': 'openstacks', # identity
'openstacks-opt08-adl': 'openstacks',
'openstacks-opt08-strips': 'openstacks',
'openstacks-opt11-strips': 'openstacks',
'openstacks-opt14-strips': 'openstacks',
'openstacks-strips': 'openstacks',
'optical-telegraphs': 'optical-telegraphs', # identity
'organic-synthesis-opt18-strips': 'organic-synthesis',
'organic-synthesis-split-opt18-strips': 'organic-synthesis-split',
'parcprinter-08-strips': 'parcprinter',
'parcprinter-opt11-strips': 'parcprinter',
'parking-opt11-strips': 'parking',
'parking-opt14-strips': 'parking',
'pathways': 'pathways', # identity
'pathways-noneg': 'pathways',
'pegsol-08-strips': 'pegsol',
'pegsol-opt11-strips': 'pegsol',
'petri-net-alignment-opt18-strips': 'petri-net-alignment',
'philosophers': 'philosophers', # identity
'pipesworld-notankage': 'pipesworld-notankage', # pipesworld?
'pipesworld-tankage': 'pipesworld-tankage', # pipesworld?
'psr-large': 'psr',
'psr-middle': 'psr',
'psr-small': 'psr',
'rovers': 'rovers', # identity
'satellite': 'satellite', # identity
'scanalyzer-08-strips': 'scanalyzer',
'scanalyzer-opt11-strips': 'scanalyzer',
'schedule': 'schedule', # identity
'settlers-opt18-adl': 'settlers',
'snake-opt18-strips': 'snake',
'sokoban-opt08-strips': 'sokoban',
'sokoban-opt11-strips': 'sokoban',
'spider-opt18-strips': 'spider',
'storage': 'storage', # identity
'termes-opt18-strips': 'termes',
'tetris-opt14-strips': 'tetris',
'tidybot-opt11-strips': 'tidybot',
'tidybot-opt14-strips': 'tidybot',
'tpp': 'tpp', # identity
'transport-opt08-strips': 'transport',
'transport-opt11-strips': 'transport',
'transport-opt14-strips': 'transport',
'trucks': 'trucks', # identity
'trucks-strips': 'trucks',
'visitall-opt11-strips': 'visitall',
'visitall-opt14-strips': 'visitall',
'woodworking-opt08-strips': 'woodworking',
'woodworking-opt11-strips': 'woodworking',
'zenotravel': 'zenotravel', # identity
}

def domain_as_category(run1, run2):
    return run1['domain']

FORMAT="png"

class FilterDomainsWithLargePruningDifference:
    def __init__(self, algorithms_of_interest):
        self.algorithms_of_interest = algorithms_of_interest
        self.domain_to_problem_to_pruning = defaultdict(dict)
        self.computed = False

    def collect_data(self, run):
        if run['algorithm'] in self.algorithms_of_interest:
            if run['problem'] not in self.domain_to_problem_to_pruning[run['domain']]:
                self.domain_to_problem_to_pruning[run['domain']][run['problem']] = []
            self.domain_to_problem_to_pruning[run['domain']][run['problem']].append(run.get('ss_pruning_ratio', None))
        return run

    def compute_interesting_domains(self, run):
        if not self.computed:
            self.computed = True
            self.interesting_domains = set()
            for domain, problem_to_pruning in self.domain_to_problem_to_pruning.items():
                for pruning in problem_to_pruning.values():
                    if len(pruning) != 2:
                        print(pruning)
                    assert len(pruning) == 2
                    # criterion of the paper
                    # if pruning[0] is not None and pruning[1] is not None and abs(pruning[0] - pruning[1]) > 0.1:
                    # any pruning
                    if pruning[0] is not None and pruning[1] is not None and (pruning[0] > 0.0 or pruning[1] > 0.0):
                        self.interesting_domains.add(domain)
            # print("interesting domains:", sorted(self.interesting_domains))
        return run

    def interesting_domains_as_category(self, run1, run2):
        if run1['domain'] in self.interesting_domains:
            return domain_groups_optimal[run1['domain']]
        return ''

for ss_comparison in [
    ('strong', 'weak'),
    ('strong', 'compliant'),
    ('strong', 'compliant_relaxed'),
    ('weak', 'compliant'),
    ('weak', 'compliant_relaxed'),
    ('compliant', 'compliant_relaxed'),
]:
    ss1 = ss_comparison[0]
    ss2 = ss_comparison[1]
    for heuristic in ['blind']:
        interesting_filter = FilterDomainsWithLargePruningDifference(
            algorithms_of_interest=[
                f'{REVISION}-{heuristic}-simple-{ss1}-min0.0',
                f'{REVISION}-{heuristic}-simple-{ss2}-min0.0']
        )

        exp.add_report(
            ScatterPlotReport(
                attributes=[ss_pruning_ratio],
                format=FORMAT,
                filter=[filter_unsolvable_tasks,interesting_filter.collect_data,interesting_filter.compute_interesting_domains],
                filter_algorithm=[
                    f'{REVISION}-{heuristic}-simple-{ss1}-min0.0',
                    f'{REVISION}-{heuristic}-simple-{ss2}-min0.0',
                ],
                show_missing=False,
                get_category=interesting_filter.interesting_domains_as_category,
                scale='linear',
            ),
            outfile=os.path.join(exp.eval_dir, f'scatter-pruningratio-{heuristic}-simple-{ss1}-{ss2}.{FORMAT}')
        )

exp.run_steps()
