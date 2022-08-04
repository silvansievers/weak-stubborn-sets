#! /usr/bin/env python3

from itertools import chain, combinations
import os
from pathlib import Path
import subprocess

from lab.environments import LocalEnvironment, BaselSlurmEnvironment
from lab.reports import Attribute, arithmetic_mean, geometric_mean

from downward.reports.compare import ComparativeReport

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
            (f'{REVISION}-{pair[0].nick}', f'{REVISION}-{pair[0].nick}') for pair in combinations(SIMPLE_CONFIGS, 2)
        ],
    ),
    name=report_name,
    outfile=report_file,
)
exp.add_step(f'publish-{report_name}', subprocess.call, ['publish', report_file])

exp.run_steps()
