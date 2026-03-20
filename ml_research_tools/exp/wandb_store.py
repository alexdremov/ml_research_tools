import json
import os
import re
from collections import defaultdict

import numpy as np
from tqdm.auto import tqdm


class ExperimentStore:
    def __init__(self, path, resolve_restarts=True):
        self.path = path
        self.resolve_restarts = resolve_restarts

        self.experiments = {}
        self._load_experiments()

    def _load_experiments(self):
        # List all JSON files in the given directory
        json_files = [f for f in os.listdir(self.path) if f.endswith(".json")]

        # Load each JSON file and store its content in self.experiments
        for file_name in tqdm(json_files, desc="Loading experiments"):
            file_path = os.path.join(self.path, file_name)
            with open(file_path, "r") as file:
                experiment_data = json.load(file)
                experiment_data[0]["run_info"]["tags"] = tuple(
                    sorted(experiment_data[0]["run_info"]["tags"])
                )
                if self.resolve_restarts:
                    experiment_data = self._resolve_restarts(experiment_data)
                self.experiments[file_name] = experiment_data

    def _resolve_restarts(self, data):
        per_step_data = defaultdict(list)
        run_info = None
        for step in data:
            step.setdefault("iteration", step.get("_step", 0))
            per_step_data[step["iteration"]].append(step)
            if "run_info" in step:
                run_info = step.pop("run_info")

        result = []
        for step in sorted(per_step_data.keys()):
            merged = dict()
            restarts_sorted = sorted(
                per_step_data[step], key=lambda x: x.get("_timestamp", x.get("_step"))
            )
            merged = restarts_sorted[0]
            for restart in restarts_sorted[1:]:
                merged |= {k: v for k, v in restart.items() if v is not None and np.isfinite(v)}
            result.append(merged)

        result[0]["run_info"] = run_info
        return result

    def get_experiment(self, file_name):
        return self.experiments.get(file_name)

    def search(self, name=None, task_id=None, tags=None, exclude_tags=None, states={"finished"}):
        all_runs = set(list(self.experiments.keys()))

        runs_tags = all_runs
        if tags is not None:
            set_tags = set(tags)
            runs_tags = set(
                k
                for k, v in self.experiments.items()
                if len(set(self.run_info(v)["tags"] or []) & set_tags) > 0
            )

        runs_names = all_runs
        if name is not None:
            runs_names = set(run for run in self.experiments.keys() if re.search(name, run))

        runs_states = all_runs
        if states is not None:
            runs_states = set(
                k for k, v in self.experiments.items() if self.run_info(v)["state"] in states
            )

        runs_task_id = all_runs
        if task_id is not None:
            runs_task_id = set(
                k for k, v in self.experiments.items() if self.run_info(v)["id"] == task_id
            )

        set_excluded = set(exclude_tags or [])
        runs_excluded = set(
            k
            for k, v in self.experiments.items()
            if len(set(self.run_info(v)["tags"] or []) & set_excluded) > 0
        )

        total_runs = (runs_tags & runs_names & runs_states & runs_task_id) - runs_excluded
        return [self.experiments[run] for run in total_runs]

    def all_tags(self, runs=None):
        return set(
            tag
            for run in (runs or self.experiments.values())
            for tag in (run[0]["run_info"]["tags"] or [])
        )

    def all_states(self, runs=None):
        return set(self.run_info(run)["state"] for run in (runs or self.experiments.values()))

    def all_task_ids(self, runs=None):
        return set(self.run_info(run)["id"] for run in (runs or self.experiments.values()))

    def all_keys(self, runs=None):
        keys = set()
        for run in runs or self.experiments.values():
            for i in run:
                keys.update(i.keys())
        return keys

    @staticmethod
    def run_info(run):
        return run[0]["run_info"]

    @staticmethod
    def run_config(run):
        return ExperimentStore.run_info(run)["config"]

    @staticmethod
    def run_summary(run):
        return ExperimentStore.run_info(run)["summary"]

    @staticmethod
    def merge_runs(runs):
        if len(runs) == 0:
            return None

        runs_sorted = sorted(runs, key=lambda x: max([i.get("_timestamp", 0) for i in x] or [0]))
        last_run = runs_sorted[-1]
        run_info = ExperimentStore.run_info(last_run)
        by_iteration = defaultdict(dict)
        for run in runs_sorted:
            for i in run:
                by_iteration[i["iteration"]] |= i

        merged = []
        for iteration in sorted(by_iteration.keys()):
            merged.append(by_iteration[iteration])
        merged[0]["run_info"] = run_info
        return merged

    @staticmethod
    def merge_runs_by_name(runs):
        by_name = defaultdict(list)
        for run in runs:
            by_name[ExperimentStore.run_info(run)["name"]].append(run)
        runs = [ExperimentStore.merge_runs(i) for i in by_name.values()]
        return runs

    @staticmethod
    def groupby(runs, key, merge=False):
        grouped = defaultdict(list)

        for run in runs:
            if callable(key):
                # If key is a function, apply it to the run
                group_key = key(run)
            else:
                # Otherwise, treat it as a path into the config
                config = ExperimentStore.run_config(run)
                run_info = ExperimentStore.run_info(run)

                # Try to get the key from config first, then run_info
                if key in config:
                    group_key = config[key]
                elif key in run_info:
                    group_key = run_info[key]
                else:
                    # Handle nested keys with dot notation (e.g., "model.type")
                    parts = key.split(".")
                    value = config

                    for part in parts:
                        if isinstance(value, dict) and part in value:
                            value = value[part]
                        else:
                            # Try run_info if not found in config
                            value = run_info
                            for p in parts:
                                if isinstance(value, dict) and p in value:
                                    value = value[p]
                                else:
                                    value = None
                                    break
                            break

                    group_key = value

                # Convert lists/dicts to tuples for hashability
                if isinstance(group_key, list):
                    group_key = tuple(group_key)
                elif isinstance(group_key, dict):
                    group_key = tuple(sorted(group_key.items()))

            grouped[group_key].append(run)
        if merge:
            grouped = {k: ExperimentStore.merge_runs(v) for k, v in grouped.items()}
        return list(grouped.values())

    @staticmethod
    def extract(run, fields, ensure_present=True):
        if run is None:
            return []
        assert isinstance(fields, list) or isinstance(fields, set)
        fields = list(set(fields))
        result = []
        for entry in run:
            row = dict()
            for field in fields:
                value = entry.get(field)
                if value is None or value == "nan" or np.isnan(value):
                    continue

                row[field] = value

            if len(row) == len(fields) or not ensure_present:
                result.append(row)

        return result
