#include "stubborn_sets.h"

#include "../option_parser.h"

#include "../task_utils/task_properties.h"
#include "../utils/logging.h"

#include <algorithm>
#include <cassert>

using namespace std;

namespace stubborn_sets {
// Relies on both fact sets being sorted by variable.
bool contain_conflicting_fact(const vector<FactPair> &facts1,
                              const vector<FactPair> &facts2) {
    auto facts1_it = facts1.begin();
    auto facts2_it = facts2.begin();
    while (facts1_it != facts1.end() && facts2_it != facts2.end()) {
        if (facts1_it->var < facts2_it->var) {
            ++facts1_it;
        } else if (facts1_it->var > facts2_it->var) {
            ++facts2_it;
        } else {
            if (facts1_it->value != facts2_it->value)
                return true;
            ++facts1_it;
            ++facts2_it;
        }
    }
    return false;
}

// Relies on both fact sets being sorted by variable.
bool contain_same_fact(const vector<FactPair> &facts1,
                       const vector<FactPair> &facts2) {
    auto facts1_it = facts1.begin();
    auto facts2_it = facts2.begin();
    while (facts1_it != facts1.end() && facts2_it != facts2.end()) {
        if (facts1_it->var < facts2_it->var) {
            ++facts1_it;
        } else if (facts1_it->var > facts2_it->var) {
            ++facts2_it;
        } else {
            if (facts1_it->value == facts2_it->value)
                return true;
            ++facts1_it;
            ++facts2_it;
        }
    }
    return false;
}

StubbornSets::StubbornSets(const Options &opts)
    : PruningMethod(opts),
      use_mutex_interference(opts.get<bool>("use_mutex_interference")),
      stubborn_set_type(opts.get<StubbornSetType>("stubborn_set_type")),
      num_operators(-1) {
    if (stubborn_set_type == stubborn_sets::StubbornSetType::COMPLIANT && use_mutex_interference) {
        cerr << "Mutex interference does not work with compliant stubborn sets" << endl;
        utils::exit_with(utils::ExitCode::SEARCH_INPUT_ERROR);
    }
}

void StubbornSets::initialize(const shared_ptr<AbstractTask> &task) {
    PruningMethod::initialize(task);
    TaskProxy task_proxy(*task);
    task_properties::verify_no_axioms(task_proxy);
    task_properties::verify_no_conditional_effects(task_proxy);

    num_operators = task_proxy.get_operators().size();
    sorted_goals = utils::sorted<FactPair>(
        task_properties::get_fact_pairs(task_proxy.get_goals()));

    compute_sorted_operators(task_proxy);
    compute_achievers(task_proxy);
}

bool StubbornSets::are_operators_mutex(int op1_no, int op2_no) const {
    const vector<FactPair> &op1_pre = sorted_op_preconditions[op1_no];
    const vector<FactPair> &op2_pre = sorted_op_preconditions[op2_no];
    for (FactPair fact1 : op1_pre) {
        FactProxy fact1_proxy(*task, fact1.var, fact1.value);
        for (FactPair fact2 : op2_pre) {
            if (fact1_proxy.is_mutex(FactProxy(*task, fact2.var, fact2.value))) {
                return true;
            }
        }
    }
    return false;
}

// Relies on op_preconds and op_effects being sorted by variable.
bool StubbornSets::can_disable(int op1_no, int op2_no) const {
    return contain_conflicting_fact(sorted_op_effects[op1_no],
                                    sorted_op_preconditions[op2_no]);
}

// Relies on op_effect being sorted by variable.
bool StubbornSets::can_conflict(int op1_no, int op2_no) const {
    return contain_conflicting_fact(sorted_op_effects[op1_no],
                                    sorted_op_effects[op2_no]);
}

// Relies on op_preconds and op_effects being sorted by variable.
bool StubbornSets::can_enable(int op1_no, int op2_no) const {
    return contain_same_fact(sorted_op_effects[op1_no],
                             sorted_op_preconditions[op2_no]);
}

void StubbornSets::compute_sorted_operators(const TaskProxy &task_proxy) {
    OperatorsProxy operators = task_proxy.get_operators();

    sorted_op_preconditions = utils::map_vector<vector<FactPair>>(
        operators, [](const OperatorProxy &op) {
            return utils::sorted<FactPair>(
                task_properties::get_fact_pairs(op.get_preconditions()));
        });

    sorted_op_effects = utils::map_vector<vector<FactPair>>(
        operators, [](const OperatorProxy &op) {
            return utils::sorted<FactPair>(
                utils::map_vector<FactPair>(
                    op.get_effects(),
                    [](const EffectProxy &eff) {return eff.get_fact().get_pair();}));
        });
}

void StubbornSets::compute_achievers(const TaskProxy &task_proxy) {
    achievers = utils::map_vector<vector<vector<int>>>(
        task_proxy.get_variables(), [](const VariableProxy &var) {
            return vector<vector<int>>(var.get_domain_size());
        });

    for (const OperatorProxy op : task_proxy.get_operators()) {
        for (const EffectProxy effect : op.get_effects()) {
            FactPair fact = effect.get_fact().get_pair();
            achievers[fact.var][fact.value].push_back(op.get_id());
        }
    }
}

bool StubbornSets::mark_as_stubborn(int op_no) {
    if (!stubborn[op_no]) {
        stubborn[op_no] = true;
        stubborn_queue.push_back(op_no);
        return true;
    }
    return false;
}

void StubbornSets::prune(const State &state, vector<OperatorID> &op_ids) {
    // Clear stubborn set from previous call.
    stubborn.assign(num_operators, false);
    assert(stubborn_queue.empty());

    initialize_stubborn_set(state);
    /* Iteratively insert operators to stubborn according to the
       definition of strong stubborn sets until a fixpoint is reached. */
    while (!stubborn_queue.empty()) {
        int op_no = stubborn_queue.back();
        stubborn_queue.pop_back();
        handle_stubborn_operator(state, op_no);
    }

    // Now check which applicable operators are in the stubborn set.
    vector<OperatorID> remaining_op_ids;
    remaining_op_ids.reserve(op_ids.size());
    for (OperatorID op_id : op_ids) {
        if (stubborn[op_id.get_index()]) {
            remaining_op_ids.emplace_back(op_id);
        }
    }
    op_ids.swap(remaining_op_ids);
}

void add_stubborn_set_options_to_parser(options::OptionParser &parser) {
    add_pruning_options_to_parser(parser);
    parser.add_option<bool>(
        "use_mutex_interference",
        "If true, consider two operators to interfere only if they interfere "
        "according to the usual definition and if they are not mutex.",
        "false");
    vector<string> stubborn_set_types;
    vector<string> stubborn_set_types_docs;
    stubborn_set_types.push_back("strong");
    stubborn_set_types_docs.push_back(
        "Strong stubborn sets. This means using regular interference.");
    stubborn_set_types.push_back("weak");
    stubborn_set_types_docs.push_back(
        "Weak stubborn sets. This means using weak interference and to include all "
        "enablers of all applicable operators in the stubborn set.)");
    stubborn_set_types.push_back("compliant");
    stubborn_set_types_docs.push_back(
        "Compliant stubborn sets. This means using weak interference.");
    parser.add_enum_option<StubbornSetType>(
        "stubborn_set_type",
        stubborn_set_types,
        "help",
        "strong",
        stubborn_set_types_docs);
}
}
