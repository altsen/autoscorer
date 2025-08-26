from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple
import csv
import math
import re
from autoscorer.schemas.result import Result
from autoscorer.utils.errors import AutoscorerError
from autoscorer.scorers.registry import register


@register("text_event_analysis")
class TextEventAnalysisScorer:
    """文本事件智能分析评分器

    目标：衡量生成报告(report/pred)与参考文档(reference/gt)之间的
    - 事实/语义一致性（ROUGE-1/2/L、Jaccard、chrF）
    - 信息覆盖度（以ROUGE-1召回为主）
    - 报告可读性与规整度（重复度、句长、标点/字符比例等）

    输入格式（CSV）：
    - input/gt.csv:    id,reference
    - output/pred.csv: id,report

    可通过 params 覆盖列名：
    - gt_text_col (默认 reference)
    - pred_text_col (默认 report)
    """

    name = "text_event_analysis"
    version = "1.0.0"

    # ---------------------------- 公共入口 ----------------------------
    def score(self, workspace: Path, params: Dict) -> Result:
        ws = Path(workspace)
        try:
            gt_col = str(params.get("gt_text_col", "reference"))
            pred_col = str(params.get("pred_text_col", "report"))

            gt_map = self._load_text_csv(ws / "input" / "gt.csv", text_col=gt_col)
            pred_map = self._load_text_csv(ws / "output" / "pred.csv", text_col=pred_col)
            self._validate_id_consistency(gt_map, pred_map)

            # 逐条计算，再做平均（macro）
            pair_metrics: List[Dict[str, float]] = []
            for k in gt_map.keys():
                ref = self._normalize_text(gt_map[k])
                hyp = self._normalize_text(pred_map[k])
                m = self._score_pair(ref, hyp)
                pair_metrics.append(m)

            metrics = self._aggregate_metrics(pair_metrics)

            # 组装summary，主评分为综合分
            score = metrics["composite_score"]
            summary = {
                "score": score,
                "factual_consistency": metrics["factual_consistency"],
                "semantic_consistency": metrics["semantic_consistency"],
                "coverage": metrics["coverage"],
                "readability": metrics["readability"],
            }

            # 等级与通过标准
            summary["rank"] = self._rank(score)
            threshold = float(params.get("pass_threshold", 0.70))
            summary["pass"] = score >= threshold

            return Result(
                summary=summary,
                metrics=metrics,
                artifacts={},
                timing={},
                resources={},
                versioning={
                    "scorer": self.name,
                    "version": self.version,
                    "algorithm": "Text Event Analysis (ROUGE/LCS/Jaccard/chrF + repetition)",
                    "timestamp": self._get_iso_timestamp(),
                },
            )
        except AutoscorerError:
            raise
        except FileNotFoundError as e:
            raise AutoscorerError(code="MISSING_FILE", message=str(e))
        except Exception as e:
            raise AutoscorerError(
                code="SCORE_ERROR",
                message=f"Text event analysis failed: {e}",
                details={"algorithm": self.name, "version": self.version},
            )

    # 新增：评分器自校验
    def validate(self, workspace: Path, params: Dict) -> None:
        ws = Path(workspace)
        gt_col = str(params.get("gt_text_col", "reference"))
        pred_col = str(params.get("pred_text_col", "report"))
        gt_map = self._load_text_csv(ws / "input" / "gt.csv", text_col=gt_col)
        pred_map = self._load_text_csv(ws / "output" / "pred.csv", text_col=pred_col)
        self._validate_id_consistency(gt_map, pred_map)

    # ---------------------------- 数据加载与校验 ----------------------------
    def _load_text_csv(self, path: Path, *, text_col: str) -> Dict[str, str]:
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        data: Dict[str, str] = {}
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise AutoscorerError(code="BAD_FORMAT", message=f"CSV no header: {path}")
            if "id" not in reader.fieldnames:
                raise AutoscorerError(code="BAD_FORMAT", message=f"Missing id column in {path}")
            if text_col not in reader.fieldnames:
                raise AutoscorerError(code="BAD_FORMAT", message=f"Missing {text_col} column in {path}")
            for i, row in enumerate(reader):
                rid = row.get("id")
                txt = row.get(text_col, "")
                if not rid:
                    raise AutoscorerError(code="BAD_FORMAT", message=f"Missing id at row {i+2} in {path}")
                if rid in data:
                    raise AutoscorerError(code="MISMATCH", message=f"Duplicate id {rid} in {path}")
                data[rid] = txt or ""
        if not data:
            raise AutoscorerError(code="BAD_FORMAT", message=f"CSV contains no data rows: {path}")
        return data

    def _validate_id_consistency(self, gt: Dict[str, str], pred: Dict[str, str]):
        a, b = set(gt.keys()), set(pred.keys())
        if a != b:
            miss = sorted(list(a - b))[:5]
            extra = sorted(list(b - a))[:5]
            msg = []
            if miss:
                msg.append(f"Missing in predictions: {miss}")
            if extra:
                msg.append(f"Extra in predictions: {extra}")
            raise AutoscorerError(code="MISMATCH", message="; ".join(msg))

    # ---------------------------- 文本与指标工具 ----------------------------
    _space_re = re.compile(r"\s+")
    _sent_split_re = re.compile(r"[。！？!?；;\n]+")

    def _normalize_text(self, s: str) -> str:
        s = (s or "").strip()
        # 统一空白
        s = self._space_re.sub(" ", s)
        return s

    def _tokenize_words(self, s: str) -> List[str]:
        # 简单分词：优先按空白；若无空白则退化为逐字符
        if not s:
            return []
        if " " in s or "\t" in s:
            toks = [t for t in self._space_re.split(s) if t]
        else:
            toks = list(s)
        return toks

    def _tokenize_chars(self, s: str) -> List[str]:
        return list(s or "")

    def _ngrams(self, seq: List[str], n: int) -> List[Tuple[str, ...]]:
        if n <= 0:
            return []
        return [tuple(seq[i : i + n]) for i in range(0, max(0, len(seq) - n + 1))]

    def _prf_from_overlap(self, ref: List[Tuple], hyp: List[Tuple]) -> Tuple[float, float, float]:
        from collections import Counter
        rc, hc = Counter(ref), Counter(hyp)
        overlap = sum((rc & hc).values())
        p = overlap / (len(hyp) or 1)
        r = overlap / (len(ref) or 1)
        f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0
        return p, r, f1

    def _lcs_len(self, a: List[str], b: List[str]) -> int:
        # O(n*m) DP，文本通常不大；必要时可截断长度
        n, m = len(a), len(b)
        if n == 0 or m == 0:
            return 0
        dp = [0] * (m + 1)
        for i in range(1, n + 1):
            prev = 0
            for j in range(1, m + 1):
                temp = dp[j]
                if a[i - 1] == b[j - 1]:
                    dp[j] = prev + 1
                else:
                    dp[j] = max(dp[j], dp[j - 1])
                prev = temp
        return dp[m]

    def _jaccard(self, a: List[str], b: List[str]) -> float:
        sa, sb = set(a), set(b)
        if not sa and not sb:
            return 1.0
        return len(sa & sb) / (len(sa | sb) or 1)

    def _distinct(self, toks: List[str], n: int) -> float:
        ng = self._ngrams(toks, n)
        if not ng:
            return 0.0
        return len(set(ng)) / len(ng)

    def _repeat_ratio(self, toks: List[str], n: int) -> float:
        from collections import Counter
        ng = self._ngrams(toks, n)
        if not ng:
            return 0.0
        c = Counter(ng)
        repeats = sum(v for v in c.values() if v > 1)
        return repeats / len(ng)

    def _chrf(self, ref_chars: List[str], hyp_chars: List[str], n: int = 6, beta: float = 2.0) -> float:
        # chrF: character n-gram F-score
        # 聚合1..n阶的平均P/R，再算F_beta
        ps, rs = [], []
        for k in range(1, n + 1):
            p, r, _ = self._prf_from_overlap(self._ngrams(ref_chars, k), self._ngrams(hyp_chars, k))
            ps.append(p)
            rs.append(r)
        P = sum(ps) / len(ps) if ps else 0.0
        R = sum(rs) / len(rs) if rs else 0.0
        if P == 0 and R == 0:
            return 0.0
        beta2 = beta * beta
        return (1 + beta2) * P * R / (beta2 * P + R) if (beta2 * P + R) > 0 else 0.0

    # ---------------------------- 单条样本打分 ----------------------------
    def _score_pair(self, ref: str, hyp: str) -> Dict[str, float]:
        ref_w = self._tokenize_words(ref)
        hyp_w = self._tokenize_words(hyp)
        ref_c = self._tokenize_chars(ref)
        hyp_c = self._tokenize_chars(hyp)

        # ROUGE-1/2（基于词/字符的简化实现：这里使用“词”序列，若无空格则退化为字符）
        # 若为中文且无空格，ref_w/hyp_w 即为字符；此时 ROUGE 等价于字符级
        r1_p, r1_r, r1_f = self._prf_from_overlap(self._ngrams(ref_w, 1), self._ngrams(hyp_w, 1))
        r2_p, r2_r, r2_f = self._prf_from_overlap(self._ngrams(ref_w, 2), self._ngrams(hyp_w, 2))

        # ROUGE-L（基于LCS的P/R/F）
        l = self._lcs_len(ref_w, hyp_w)
        rl_p = l / (len(hyp_w) or 1)
        rl_r = l / (len(ref_w) or 1)
        rl_f = (2 * rl_p * rl_r / (rl_p + rl_r)) if (rl_p + rl_r) > 0 else 0.0

        # 信息覆盖度：采用 ROUGE-1 Recall
        coverage = r1_r

        # 语义一致性：Jaccard（去重后的词集合）与 chrF 的加权最大
        jacc = self._jaccard(ref_w, hyp_w)
        chrf = self._chrf(ref_c, hyp_c, n=6, beta=2.0)
        semantic = max(jacc, chrf)

        # 可读性与规整度：重复度越低越好；句长适中（以20~40词最优）
        sent_lens = [len(self._tokenize_words(s)) for s in self._sent_split_re.split(hyp) if s.strip()]
        avg_sent_len = (sum(sent_lens) / len(sent_lens)) if sent_lens else len(hyp_w)
        # 以高斯型奖励 20~40 之间
        mu, sigma = 30.0, 10.0
        len_score = math.exp(-((avg_sent_len - mu) ** 2) / (2 * sigma * sigma))
        rep3 = self._repeat_ratio(hyp_w, 3)
        rep2 = self._repeat_ratio(hyp_w, 2)
        distinct1 = self._distinct(hyp_w, 1)
        distinct2 = self._distinct(hyp_w, 2)
        readability = max(0.0, min(1.0, 0.6 * len_score + 0.2 * distinct1 + 0.2 * distinct2))
        repetition_penalty = min(0.2, 0.5 * rep3 + 0.25 * rep2)  # 上限0.2

        # 事实一致性：更看重 ROUGE-2 与 ROUGE-L
        factual = 0.4 * r2_f + 0.6 * rl_f

        # 综合分：权重可通过 params 调整（此处使用默认）
        composite = (
            0.4 * factual + 0.3 * semantic + 0.2 * coverage + 0.1 * readability - repetition_penalty
        )
        composite = max(0.0, min(1.0, composite))

        return {
            # ROUGE
            "rouge1_p": r1_p,
            "rouge1_r": r1_r,
            "rouge1_f": r1_f,
            "rouge2_p": r2_p,
            "rouge2_r": r2_r,
            "rouge2_f": r2_f,
            "rougeL_p": rl_p,
            "rougeL_r": rl_r,
            "rougeL_f": rl_f,
            # LCS
            "lcs_len": float(l),
            "lcs_ratio": (l / (len(ref_w) or 1)),
            # 语义/覆盖
            "semantic_jaccard": jacc,
            "chrf": chrf,
            "semantic_consistency": semantic,
            "coverage": coverage,
            # 可读性/规整度
            "avg_sentence_length": float(avg_sent_len),
            "distinct_1": distinct1,
            "distinct_2": distinct2,
            "repeat_2gram": rep2,
            "repeat_3gram": rep3,
            "readability": readability,
            # 事实一致性、综合
            "factual_consistency": factual,
            "repetition_penalty": repetition_penalty,
            "composite_score": composite,
        }

    # ---------------------------- 汇总 ----------------------------
    def _aggregate_metrics(self, rows: List[Dict[str, float]]) -> Dict[str, float]:
        if not rows:
            return {"composite_score": 0.0}
        keys = rows[0].keys()
        out: Dict[str, float] = {}
        for k in keys:
            # 平均（对 avg_sentence_length 这类量纲不同的指标平均也可接受，仅作参考输出）
            out[k] = float(sum(r.get(k, 0.0) for r in rows) / len(rows))
        # 附带样本数
        out["samples"] = float(len(rows))
        return out

    # ---------------------------- 杂项 ----------------------------
    def _rank(self, score: float) -> str:
        if score >= 0.85:
            return "A"
        if score >= 0.75:
            return "B"
        if score >= 0.65:
            return "C"
        return "D"

    # 与 BaseCSVScorer 对齐的时间戳工具（避免引入基类）
    def _get_iso_timestamp(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
