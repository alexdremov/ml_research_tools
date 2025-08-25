import itertools
import os
import re
import json
from tqdm.auto import tqdm
from collections import defaultdict


class ExperimentStore:
    def __init__(self, path):
        self.path = path
        self.experiments = {}
        self._load_experiments()

    def _load_experiments(self):
        # List all JSON files in the given directory
        json_files = [f for f in os.listdir(self.path) if f.endswith('.json')]

        # Load each JSON file and store its content in self.experiments
        for file_name in tqdm(json_files, desc="Loading experiments"):
            file_path = os.path.join(self.path, file_name)
            with open(file_path, 'r') as file:
                experiment_data = json.load(file)
                experiment_data[0]['run_info']['tags'] = tuple(sorted(experiment_data[0]['run_info']['tags']))
                self.experiments[file_name] = experiment_data

    def get_experiment(self, file_name):
        return self.experiments.get(file_name)

    def search(self, name=None, tags=None, exclude_tags=None, states={'finished'}):
        all_runs = set(list(self.experiments.keys()))

        runs_tags = all_runs
        if tags is not None:
            set_tags = set(tags)
            runs_tags = set(
                k for k, v in self.experiments.items()
                if len(set(self.run_info(v)['tags'] or []) & set_tags) > 0
            )

        runs_names = all_runs
        if name is not None:
            runs_names = set(run for run in self.experiments.keys() if re.search(name, run))

        runs_states = all_runs
        if states is not None:
            runs_states = set(
                k for k, v in self.experiments.items()
                if self.run_info(v)['state'] in states
            )

        set_excluded= set(exclude_tags or [])
        runs_excluded = set(
                k for k, v in self.experiments.items()
                if len(set(self.run_info(v)['tags'] or []) & set_excluded) > 0
            )

        total_runs = (runs_tags & runs_names & runs_states) - runs_excluded
        return [
            self.experiments[run] for run in total_runs
        ]

    @property
    def all_tags(self):
        return set(tag for runs in self.experiments.values() for tag in (runs[0]['run_info']['tags'] or []))

    @property
    def all_states(self):
        return set(self.run_info(run)['state'] for run in self.experiments.values())

    @staticmethod
    def run_info(run):
        return run[0]['run_info']

    @staticmethod
    def run_config(run):
        return ExperimentStore.run_info(run)['config']

    @staticmethod
    def run_summary(run):
        return ExperimentStore.run_info(run)['summary']


    @staticmethod
    def merge_runs(runs):
        last_run = max(
            runs,
            key=lambda x: max(i.get('_timestamp', 0) for i in x)
        )
        run_info = ExperimentStore.run_info(last_run)
        merged = []
        for run in runs:
            merged.extend(
                {
                    k: v
                    for k, v in i.items()
                    if k != 'run_info'
                }
                for i in run
            )
        merged.sort(key=lambda x: x['_timestamp'])
        merged[0]['run_info'] = run_info
        return merged


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
                    parts = key.split('.')
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
