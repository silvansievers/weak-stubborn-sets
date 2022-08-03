#! /usr/bin/env python

from lab.parser import Parser

parser = Parser()
parser.add_pattern('ss_successors_unpruned', 'total successors before partial-order reduction: (\d+)', required=False, type=int)
parser.add_pattern('ss_successors_pruned', 'total successors after partial-order reduction: (\d+)', required=False, type=int)
parser.add_pattern('ss_pruning_ratio', 'Pruning ratio: (.+)', required=False, type=float)
parser.add_pattern('ss_pruning_time', 'Time for pruning operators: (.+)s', required=False, type=float)

parser.parse()
