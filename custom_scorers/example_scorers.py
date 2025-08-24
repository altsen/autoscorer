"""
示例自定义评分器
"""
import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error

class CustomMAEScorer:
    """自定义MAE评分器示例"""
    
    SCORER_NAME = "custom_mae"  # 指定注册名称
    
    def score(self, gt_path: str, pred_path: str) -> dict:
        """计算MAE分数"""
        gt_df = pd.read_csv(gt_path)
        pred_df = pd.read_csv(pred_path)
        
        # 假设都有'target'列
        gt_values = gt_df['target'].values
        pred_values = pred_df['target'].values
        
        mae = mean_absolute_error(gt_values, pred_values)
        
        return {
            'ok': True,
            'summary': {'mae': float(mae)},
            'details': {
                'metric': 'mean_absolute_error',
                'samples': len(gt_values)
            }
        }

class CustomMAPEScorer:
    """自定义MAPE评分器示例"""
    
    SCORER_NAME = "custom_mape"
    
    def score(self, gt_path: str, pred_path: str) -> dict:
        """计算MAPE分数"""
        gt_df = pd.read_csv(gt_path)
        pred_df = pd.read_csv(pred_path)
        
        gt_values = gt_df['target'].values
        pred_values = pred_df['target'].values
        
        # 避免除零
        mask = gt_values != 0
        mape = np.mean(np.abs((gt_values[mask] - pred_values[mask]) / gt_values[mask])) * 100
        
        return {
            'ok': True,
            'summary': {'mape': float(mape)},
            'details': {
                'metric': 'mean_absolute_percentage_error',
                'samples': len(gt_values),
                'valid_samples': np.sum(mask)
            }
        }
