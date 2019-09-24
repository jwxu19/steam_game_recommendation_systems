#!/usr/bin/env python3
from surprise import KNNWithMeans, SVD, SVDpp, SlopeOne, CoClustering
from surprise import Reader, Dataset, accuracy, model_selection
import random
import time
import re
import pickle

from os.path import abspath, dirname, join
import numpy as np
from recsys.evaluate import (
    precision_recall_at_k, personalization, metrics_dataframe, show_results)


DATA_DIR = join(dirname(dirname(abspath((__file__)))), "data")
PKL_FILE = join(DATA_DIR, "data_after_filter.pkl")
METRICS_FILE = join(DATA_DIR, "metrics.pkl")
OUTPUT_FILE = join(DATA_DIR, "best_model_predictions.pkl")


def load_filtered_data(file=PKL_FILE):
    f = open(file, "rb")
    data = pickle.load(f)
    f.close()
    return data


def save_metrics(metrics, file=METRICS_FILE):
    f = open(file, "wb")
    pickle.dump(metrics, f)
    f.close()


def save_output(output, file=OUTPUT_FILE):
    f = open(file, "wb")
    pickle.dump(output, f)
    f.close()


def set_seed():
    seed = 0
    random.seed(seed)
    np.random.seed(seed)


def iterate_algo(algo_ls, kfold, data, top_n, threshold, k_ls):

    kf = model_selection.KFold(n_splits=kfold)

    metrics = {"cv_rmse": [],
               "cv_precision": [],
               "cv_recall": [],
               "cv_fit_time": [],
               "cv_pred_time": [],
               "cv_personalization": [],
               "algo_name": []}

    for algo in algo_ls:
        rmse_ls = []
        precisions_dict = {}
        recalls_dict = {}
        fit_time_ls = []
        pred_time_ls = []
        personalization_ls = []

        # perform cross vailidation
        for train, test in kf.split(data):

            fit_start = time.time()
            algo.fit(train)
            fit_time = time.time() - fit_start

            pred_start = time.time()
            pred = algo.test(test)
            pred_time = time.time() - pred_start

            rmse = accuracy.rmse(pred)
            rmse_ls.append(rmse)

            # iterate k_ls
            for k in k_ls:

                precisions, recalls = precision_recall_at_k(
                    pred, k, threshold)

                if k in precisions_dict:
                    precisions_dict[k].append(precisions)
                else:
                    precisions_dict[k] = [precisions]

                if k in recalls_dict:
                    recalls_dict[k].append(recalls)
                else:
                    recalls_dict[k] = [recalls]

            personalization_ls.append(personalization(pred, top_n))

            fit_time_ls.append(fit_time)
            pred_time_ls.append(pred_time)

        metrics["cv_rmse"].append(rmse_ls)
        metrics["cv_precision"].append(precisions_dict)
        metrics["cv_recall"].append(recalls_dict)

        metrics["cv_personalization"].append(personalization_ls)
        metrics["cv_fit_time"].append(fit_time_ls)
        metrics["cv_pred_time"].append(pred_time_ls)

        regex = r"(\w+)\s"
        name = re.search(regex, str(algo))
        metrics["algo_name"].append(name.group())

    return metrics


def find_best_model(algo_dict, metrics, rank_by="rmse", k=10):
    df_precision, df_recall, df_general_metrics = metrics_dataframe(
        metrics)

    if rank_by in ["rmse", "fit_time", "pred_time"]:
        best_algo_name = list(df_general_metrics.sort_values(
            by=rank_by, ascending=True).index)[0]
    elif rank_by == "persoanalization":
        best_algo_name = list(df_general_metrics.sort_values(
            by=rank_by, ascending=False).index)[0]
    elif rank_by == "precision":
        best_algo_name = list(df_precision.T.sort_values(
            by=k, ascending=False).index)[0]
    elif rank_by == "recall":
        best_algo_name = list(df_recall.T.sort_values(
            by=k, ascending=False).index)[0]
    return algo_dict[best_algo_name]


def refit(data, best_algo):
    # fit algorithm to the whole dataset
    trainset = data.build_full_trainset()
    best_algo.fit(trainset)
    testset = trainset.build_testset()
    predictions = best_algo.test(testset)
    output = {"predictions": predictions, "algo": best_algo}
    return output


def main():
    set_seed()
    data = load_filtered_data()
    data = Dataset.load_from_df(data, reader=Reader(rating_scale=(1, 5)))

    kfold = 5
#    algo_ls = (KNNWithMeans(), SVD())
    algo_ls = (KNNWithMeans(),
               SVD(), SVDpp(),
               SlopeOne(), CoClustering())
    top_n = 10
    threshold = 4
    k_ls = [3, 5, 7, 10]
    metrics = iterate_algo(algo_ls, kfold, data, top_n, threshold, k_ls)
    algo_dict = dict(zip(metrics["algo_name"], algo_ls))

    output = refit(data, find_best_model(algo_dict, metrics))
    save_output(output)
    save_metrics(metrics)
    show_results(metrics)


if __name__ == "__main__":
    main()
