# Copyright (c) OpenMMLab. All rights reserved.
import os.path as osp

from .builder import DATASETS
from .custom import CustomDataset
from collections import OrderedDict

from mmseg.core import eval_metrics, intersect_and_union, pre_eval_to_metrics
import mmcv
import numpy as np
from mmcv.utils import print_log
from prettytable import PrettyTable
from mmseg.core import eval_metrics
import os
from sklearn import metrics

@DATASETS.register_module()
class HSIDataset(CustomDataset):
    """Pascal VOC dataset.

    Args:
        split (str): Split txt file for Pascal VOC.
    """

    CLASSES = ('noncancer', 'cancer')

    PALETTE = [[0, 0, 0], [255, 255, 255]]

    def __init__(self, split, **kwargs):
        super(HSIDataset, self).__init__(
            img_suffix='.hdr', seg_map_suffix='.png', split=split, **kwargs)
        assert osp.exists(self.img_dir) and self.split is not None


    def evaluate(self,
                 results,
                 metric='mIoU',
                 logger=None,
                 gt_seg_maps=None,
                 **kwargs):

        """Evaluate the dataset.

        Args:
            results (list[tuple[torch.Tensor]] | list[str]): per image pre_eval
                 results or predict segmentation map for computing evaluation
                 metric.
            metric (str | list[str]): Metrics to be evaluated. 'mIoU',
                'mDice' and 'mFscore' are supported.
            logger (logging.Logger | None | str): Logger used for printing
                related information during evaluation. Default: None.
            gt_seg_maps (generator[ndarray]): Custom gt seg maps as input,
                used in ConcatDataset

        Returns:
            dict[str, float]: Default metrics.
        """
        if isinstance(metric, str):
            metric = [metric]
        allowed_metrics = ['mIoU', 'mDice', 'mFscore']
        if not set(metric).issubset(set(allowed_metrics)):
            raise KeyError('metric {} is not supported'.format(metric))

        eval_results = {}
        # test a list of files
        if mmcv.is_list_of(results, np.ndarray) or mmcv.is_list_of(
                results, str):
            if gt_seg_maps is None:
                gt_seg_maps = self.get_gt_seg_maps()
            num_classes = len(self.CLASSES)
            ret_metrics = eval_metrics(
                results,
                gt_seg_maps,
                num_classes,
                self.ignore_index,
                metric,
                label_map=self.label_map,
                reduce_zero_label=self.reduce_zero_label)

            # get kappa
            con_mat = np.zeros((2, 2))
            for result, gt in zip(results, self.get_gt_seg_maps()):
                con_mat += metrics.confusion_matrix(gt.flatten(), result.flatten(), labels=[1, 0])

        # test a list of pre_eval_results
        else:
            ret_metrics = pre_eval_to_metrics(results, metric)

            # get kappa
            con_mat = np.zeros((2, 2))
            pre_eval_results = tuple(zip(*results))

            total_area_intersect = sum(pre_eval_results[0])
            total_area_label = sum(pre_eval_results[3])
            con_mat[0][0] = total_area_intersect[0]
            con_mat[1][1] = total_area_intersect[1]
            con_mat[0][1] = total_area_label[1] - total_area_intersect[1]
            con_mat[1][0] = total_area_label[0] - total_area_intersect[0]

        # Because dataset.CLASSES is required for per-eval.
        if self.CLASSES is None:
            class_names = tuple(range(num_classes))
        else:
            class_names = self.CLASSES

        # summary table
        ret_metrics_summary = OrderedDict({
            ret_metric: np.round(np.nanmean(ret_metric_value) * 100, 2)
            for ret_metric, ret_metric_value in ret_metrics.items()
        })

        # each class table
        ret_metrics.pop('aAcc', None)
        ret_metrics_class = OrderedDict({
            ret_metric: np.round(ret_metric_value * 100, 2)
            for ret_metric, ret_metric_value in ret_metrics.items()
        })
        ret_metrics_class.update({'Class': class_names})
        ret_metrics_class.move_to_end('Class', last=False)

        # for logger
        class_table_data = PrettyTable()
        for key, val in ret_metrics_class.items():
            class_table_data.add_column(key, val)

        summary_table_data = PrettyTable()
        for key, val in ret_metrics_summary.items():
            if key == 'aAcc':
                summary_table_data.add_column(key, [val])
            else:
                summary_table_data.add_column('m' + key, [val])

        print_log('per class results:', logger)
        print_log('\n' + class_table_data.get_string(), logger=logger)
        print_log('Summary:', logger)
        print_log('\n' + summary_table_data.get_string(), logger=logger)

        # each metric dict
        for key, value in ret_metrics_summary.items():
            if key == 'aAcc':
                eval_results[key] = value / 100.0
            else:
                eval_results['m' + key] = value / 100.0

        ret_metrics_class.pop('Class', None)
        for key, value in ret_metrics_class.items():
            eval_results.update({
                key + '.' + str(name): value[idx] / 100.0
                for idx, name in enumerate(class_names)
            })

        print_log('accuracy:{}'.format(accuracy(con_mat)), logger=logger)
        print_log('kappa:{}'.format(kappa(con_mat)), logger=logger)
        print_log('mIoU:{}'.format(eval_results['mIoU']), logger=logger)
        print_log('mDice:{}'.format(eval_results['mDice']), logger=logger)
        # print_log('precision:{}'.format(precision(con_mat)), logger=logger)
        # print_log('sensitivity:{}'.format(sensitivity(con_mat)), logger=logger)
        # print_log('specificity:{}'.format(specificity(con_mat)), logger=logger)

        return eval_results


def kappa(matrix):
    matrix = np.array(matrix)
    n = np.sum(matrix)
    sum_po = 0
    sum_pe = 0
    for i in range(len(matrix[0])):
        sum_po += matrix[i][i]
        row = np.sum(matrix[i, :])
        col = np.sum(matrix[:, i])
        sum_pe += row * col
    po = sum_po / n
    pe = sum_pe / (n * n)
    # print(po, pe)
    return (po - pe) / (1 - pe)
def sensitivity(matrix):
    return matrix[0][0]/(matrix[0][0]+matrix[1][0])
def specificity(matrix):
    return matrix[1][1]/(matrix[1][1]+matrix[0][1])
def precision(matrix):
    return matrix[0][0]/(matrix[0][0]+matrix[0][1])
def accuracy(matrix):
    return (matrix[0][0]+matrix[1][1])/(matrix[0][0]+matrix[0][1]+matrix[1][0]+matrix[1][1])