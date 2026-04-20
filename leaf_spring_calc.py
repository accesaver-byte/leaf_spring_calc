"""
板簧参数计算 Web 工具
辰赛汽车配件 — Leaf Spring Calculator
运行: streamlit run leaf_spring_calc.py
"""

import math
import numpy as np
import pandas as pd
import streamlit as st
from scipy.optimize import brentq

# ============================================================
# 模型 1: 单片几何参数互算
# ============================================================

def model1_forward(D, H, r, t):
    """单片板簧几何计算。D=弦长半长, H=自由弧高, r=卷耳内半径, t=片厚"""
    R = ((2 * D) ** 2 + 4 * (H - r) ** 2) / (8 * (H - r)) + r
    alpha_deg = math.degrees(math.asin(D / (R - r)))
    s = 2 * math.pi * (R + t / 2) * alpha_deg / 360
    return {
        "弦长半长 D": D,
        "自由弧高 H": H,
        "卷耳内半径 r": r,
        "片厚 t": t,
        "曲率半径 R": R,
        "夹角 α (°)": alpha_deg,
        "伸直半长 s": s,
        "弦长全长 2D": 2 * D,
        "伸直全长 2s": 2 * s,
    }


# ============================================================
# 模型 2: 非对称板簧弧高
# ============================================================

def model2_forward(total_straight, center_arc, flat_len, short_straight, short_dia, long_dia):
    """非对称板簧弧高计算"""
    long_straight = total_straight - short_straight
    avg_dia = (short_dia / 2 + long_dia / 2) / 2
    R = (total_straight - flat_len) ** 2 / (8 * (center_arc - avg_dia))
    H_short = (short_straight * 2 - flat_len) ** 2 / (8 * R) + short_dia / 2 + 1
    H_long = (long_straight * 2 - flat_len) ** 2 / (8 * R) + long_dia / 2 + 1
    return {
        "伸直全长": total_straight,
        "中心弧高": center_arc,
        "中间平直段长": flat_len,
        "短端伸直长": short_straight,
        "长端伸直长": long_straight,
        "短端卷耳孔径": short_dia,
        "长端卷耳孔径": long_dia,
        "R (参考)": R,
        "弧高H (短端)": H_short,
        "弧高H (长端)": H_long,
    }


# ============================================================
# 模型 3: 圆弧多片弧高计算
# ============================================================

def model3_forward(data, variant="standard"):
    """
    圆弧多片弧高计算。
    data: list of dict, 每片含 B(伸直长), F1(第1片喷丸后弧高,仅第1片需要), G(间隙), K(厚度), L(喷丸系数)
    variant: "standard" 用 B 直接计算, "with_halflen" 用 弧长-平直段 (Sheet1(7) 变体)
    对于 variant="with_halflen", 每片还需 arc_len(弧长) 和可选 flat_seg(平直段长,默认0)
    """
    n = len(data)
    results = []

    for i in range(n):
        row = data[i]
        if variant == "with_halflen":
            B_eff = row.get("arc_len", row["B"]) - row.get("flat_seg", 0)
        else:
            B_eff = row["B"]

        K = row["K"]
        L_coeff = row.get("L", 0.0005)
        G = row.get("G", 0)

        if i == 0:
            F = row["F1"]
        else:
            prev = data[i - 1]
            if variant == "with_halflen":
                B_prev_eff = prev.get("arc_len", prev["B"]) - prev.get("flat_seg", 0)
            else:
                B_prev_eff = prev["B"]
            F_prev = results[i - 1]["喷丸后弧高 F"]
            F = (B_eff ** 2 / B_prev_eff ** 2) * F_prev + G

        E = (B_eff / K) ** 2 * L_coeff  # 变形量
        C = F + E  # 淬火弧高
        R_val = B_eff ** 2 / (8 * C)  # 曲率半径
        H_ratio = F / B_eff  # 比率

        results.append({
            "序号": i + 1,
            "伸直长 B": row["B"],
            "喷丸后弧高 F": F,
            "淬火弧高 C": C,
            "曲率半径 R": R_val,
            "变形量 E": E,
            "间隙 G": G,
            "厚度 K": K,
            "喷丸系数 L": L_coeff,
            "比率 H=F/B": H_ratio,
        })

    # 总成弧高计算
    sum_H = sum(r["比率 H=F/B"] for r in results)  # 喷丸后弧高比率
    sum_N = sum(r["淬火弧高 C"] / r["伸直长 B"] for r in results)  # 淬火弧高比率
    sum_B = sum(r["伸直长 B"] for r in results)
    if variant == "standard":
        B1 = results[0]["伸直长 B"]
    else:
        B1 = data[0].get("arc_len", data[0]["B"]) - data[0].get("flat_seg", 0)
    assembly_arc_F = B1 ** 2 * sum_H / sum_B if sum_B > 0 else 0
    assembly_arc_C = B1 ** 2 * sum_N / sum_B if sum_B > 0 else 0

    return results, {
        "Σ(F/B) 喷丸比率": sum_H,
        "Σ(C/B) 淬火比率": sum_N,
        "Σ(B)": sum_B,
        "总成弧高 (喷丸后)": assembly_arc_F,
        "总成弧高 (淬火后)": assembly_arc_C,
    }


def model3_with_eye(data, eye_radius=0):
    """Sheet1(7) 变体: 带卷耳内半径修正"""
    results, summary = model3_forward(data, variant="with_halflen")
    assembly_arc = summary["总成弧高 (淬火后)"]
    summary["卷耳内半径"] = eye_radius
    summary["总成弧高 (带卷耳)"] = assembly_arc + eye_radius
    # 第1片加端垫后弧高
    if results:
        summary["第1片淬火弧高+卷耳"] = results[0]["淬火弧高 C"] + eye_radius
    return results, summary


# ============================================================
# 模型 4: 卷耳展开/下料长度
# ============================================================

def model4a_simple_eye(D_dia, L_body, h_thick, both_ends=True):
    """4a: 简单卷耳(3/4圈)"""
    PI = 3.14  # 与Excel公式一致
    unroll = (D_dia + h_thick) * PI * 3 / 4 + D_dia * PI / 4 + L_body
    cut_single = unroll + 4
    cut_total = cut_single * 2 if both_ends else cut_single
    return {
        "卷耳孔径 D": D_dia,
        "板身长度 L": L_body,
        "板簧厚度 h": h_thick,
        "展开半长": unroll,
        "断料半长": cut_single,
        "断料全长": cut_total,
    }


def model4a_quarter(D_dia, L_body, h_thick):
    """4a: 1/4包耳"""
    PI = 3.14  # 与Excel公式一致
    R = (D_dia + h_thick * 2) / 2
    cut_len = (R + h_thick / 2) * 2 * PI * 90 / 360 + L_body + 5
    return {
        "卷耳孔径 D": D_dia,
        "板身长度 L": L_body,
        "板簧厚度 h": h_thick,
        "包耳半径 R": R,
        "下料半长": cut_len,
    }


def model4b_arc_eye(D_dia, L_body, h_thick, R_arc):
    """4b: 带圆弧过渡卷耳"""
    PI = 3.14  # 与Excel公式一致
    A = R_arc + h_thick / 2
    B = h_thick + R_arc + D_dia / 2
    C = math.sqrt(B ** 2 - A ** 2)
    theta = math.acos(A / B)
    unroll = theta * B + (D_dia + h_thick) * PI * 3 / 4 + L_body - C
    cut_single = unroll + 10  # 加余量
    return {
        "卷耳孔径 D": D_dia,
        "板身长度 L": L_body,
        "板簧厚度 h": h_thick,
        "圆弧半径 R_arc": R_arc,
        "A": A,
        "B": B,
        "C": C,
        "θ (rad)": theta,
        "θ (°)": math.degrees(theta),
        "展开半长": unroll,
        "断料半长": cut_single,
        "断料全长": cut_single * 2,
    }


def model4c_wrap2(D_dia, L_body, h_thick, h1_core, H_open, r_arc):
    """4c: 二片包耳"""
    PI = 3.14159  # 与Excel公式一致
    R_wrap = (D_dia + 2 * h_thick + 4) / 2
    # L1: 1/4圈
    L1 = 2 * PI * (R_wrap + h_thick / 2) * 0.25
    # 角度
    angle_rad = math.acos((r_arc + h_thick + h1_core + 2) / (r_arc + h_thick + R_wrap))
    angle_deg = math.degrees(angle_rad)
    # L3: 圆弧过渡段
    L3 = 2 * PI * (r_arc + h_thick / 2) * angle_deg / 360
    # L2: 包耳弧段
    L2 = 2 * PI * (R_wrap + h_thick / 2) * angle_deg / 360
    # L4: 弦长
    L4 = math.sqrt((R_wrap + h_thick + r_arc) ** 2 - (r_arc + h_thick + h1_core + 2) ** 2) + 4
    unroll = L_body - L4 + L1 + L3 + L2 + 3
    return {
        "卷耳孔径 D": D_dia,
        "板身长度 L": L_body,
        "板簧厚度 h": h_thick,
        "芯部高度 h1": h1_core,
        "开口高度 H": H_open,
        "圆弧半径 r": r_arc,
        "包耳R": R_wrap,
        "L1 (1/4圈)": L1,
        "角度 (°)": angle_deg,
        "L2 (包耳弧)": L2,
        "L3 (过渡弧)": L3,
        "L4 (弦长)": L4,
        "展开半长": unroll,
        "展开全长": unroll * 2,
    }


def model4d_wrap3(D_dia, L_body, h_thick, h1_core, H_open, r_arc, extra_h=0):
    """4d: 三片包耳 (R递增)"""
    PI = 3.14159  # 与Excel公式一致
    R_wrap = (D_dia + 2 * h_thick + 4) / 2 + h_thick + 2  # 在二片基础上增加
    if extra_h > 0:
        R_wrap = (D_dia + 2 * h_thick + 4) / 2 + extra_h
    L1 = 2 * PI * (R_wrap + h_thick / 2) * 0.25
    angle_rad = math.acos((r_arc + h_thick + h1_core + 2) / (r_arc + h_thick + R_wrap))
    angle_deg = math.degrees(angle_rad)
    L3 = 2 * PI * (r_arc + h_thick / 2) * angle_deg / 360
    L2 = 2 * PI * (R_wrap + h_thick / 2) * angle_deg / 360
    L4 = math.sqrt((R_wrap + h_thick + r_arc) ** 2 - (r_arc + h_thick + h1_core + 2) ** 2) + 4
    unroll = L_body - L4 + L1 + L3 + L2 + 3 - 8  # 三片有额外扣减
    return {
        "卷耳孔径 D": D_dia,
        "板身长度 L": L_body,
        "板簧厚度 h": h_thick,
        "芯部高度 h1": h1_core,
        "开口高度 H": H_open,
        "圆弧半径 r": r_arc,
        "包耳R": R_wrap,
        "L1 (1/4圈)": L1,
        "角度 (°)": angle_deg,
        "L2 (包耳弧)": L2,
        "L3 (过渡弧)": L3,
        "L4 (弦长)": L4,
        "展开半长": unroll,
        "展开全长": unroll * 2,
    }


def calc_weight(width_mm, thick_mm, length_mm):
    """重量 (kg)"""
    return width_mm * thick_mm * 7.85 * length_mm / 1_000_000


# ============================================================
# 模型 5: 变截面总成弧高
# ============================================================

def model5_forward(data, shot_coeff=0.0005, eye_dia=0):
    """
    变截面总成弧高计算。
    data: list of dict, 每片含:
        B(伸直长), C(平直段长), G(厚度), H_end(后片端部厚度),
        F_gap(间隙,第1片无), I_noise(降噪片厚度,默认0), J_shim(垫片厚度,默认0)
    第1片还需 E1(等长弧高初值)
    """
    n = len(data)
    results = []

    for i in range(n):
        row = data[i]
        B = row["B"]
        C_flat = row.get("C", 0)
        D = B - C_flat  # 去平直段伸直长
        G_thick = row["G"]
        H_end = row.get("H_end", G_thick)
        I_noise = row.get("I_noise", 0)
        J_shim = row.get("J_shim", 0)
        F_gap = row.get("F_gap", 0)

        if i == 0:
            E = row["E1"]
            K = E  # 等长有效弧高
        else:
            prev = data[i - 1]
            G_prev = prev["G"]
            H_prev = prev.get("H_end", G_prev)
            E = results[i - 1]["等长弧高 E"] + F_gap + G_prev - H_prev + J_shim - I_noise
            K = E - G_prev + H_prev + I_noise - J_shim

        # 喷丸后弧高
        if i == 0:
            L = E
        else:
            D_prev = data[i - 1]["B"] - data[i - 1].get("C", 0)
            L = (D ** 2 / D_prev ** 2) * E

        # 变形量
        avg_thick = (G_thick + H_end) / 2
        O = (B / avg_thick) ** 2 * shot_coeff

        # 淬火弧高
        P = L + O

        results.append({
            "序号": i + 1,
            "伸直长 B": B,
            "平直段 C": C_flat,
            "去平直段 D": D,
            "等长弧高 E": E,
            "等长有效弧高 K": K,
            "喷丸后弧高 L": L,
            "板厚 G": G_thick,
            "端部厚 H": H_end,
            "间隙 F": F_gap,
            "降噪片 I": I_noise,
            "垫片 J": J_shim,
            "变形量 O": O,
            "淬火弧高 P": P,
        })

    # 总成弧高
    sum_K = sum(r["等长有效弧高 K"] for r in results)
    count = len(results)
    assembly_no_eye = sum_K / count if count > 0 else 0
    assembly_with_eye = assembly_no_eye + eye_dia / 2

    # 淬火弧高有效值之和
    sum_Q = sum(r["等长有效弧高 K"] + r["变形量 O"] for r in results)

    return results, {
        "片数": count,
        "Σ(K)": sum_K,
        "装配总成弧高 (不带卷耳)": assembly_no_eye,
        "卷耳孔径": eye_dia,
        "样板总成弧高 (带卷耳)": assembly_with_eye,
        "Σ(Q) 淬火有效弧高之和": sum_Q,
        "样板总成弧高 (淬火有效/片数)": sum_Q / count if count > 0 else 0,
        "样板总成弧高+卷耳": sum_Q / count + eye_dia / 2 if count > 0 else 0,
    }


# ============================================================
# 通用单变量求解器
# ============================================================

def solve_single_variable(calc_func, params, solve_var, target_var, target_val,
                          bounds=(0.01, 10000), tol=1e-8):
    """
    通用单变量求解：在 params 中把 solve_var 作为未知量，
    使目标函数 calc_func(params) 的 target_var 输出等于 target_val。
    """
    original = params[solve_var]

    def objective(x):
        params[solve_var] = x
        try:
            result = calc_func(**params)
            return result[target_var] - target_val
        except (ValueError, ZeroDivisionError, ArithmeticError):
            return float('inf')

    try:
        solution = brentq(objective, bounds[0], bounds[1], xtol=tol, maxiter=200)
        params[solve_var] = solution
        return solution, calc_func(**params)
    except ValueError:
        params[solve_var] = original
        return None, None


# ============================================================
# Streamlit UI
# ============================================================

def main():
    st.set_page_config(page_title="板簧参数计算", layout="wide")
    st.title("板簧参数计算工具")
    st.caption("辰赛汽车配件 — Leaf Spring Calculator")

    model = st.sidebar.selectbox(
        "选择计算模型",
        [
            "模型1: 单片几何参数互算",
            "模型2: 非对称板簧弧高",
            "模型3: 圆弧多片弧高计算",
            "模型4: 卷耳展开/下料长度",
            "模型5: 变截面总成弧高",
        ],
    )

    if model.startswith("模型1"):
        ui_model1()
    elif model.startswith("模型2"):
        ui_model2()
    elif model.startswith("模型3"):
        ui_model3()
    elif model.startswith("模型4"):
        ui_model4()
    elif model.startswith("模型5"):
        ui_model5()


# ------ 模型1 UI ------
def ui_model1():
    st.header("模型1: 单片几何参数互算")
    st.markdown("支持 **卷耳片** (r > 0) 和 **简单直片** (r = 0)")

    col1, col2 = st.columns(2)
    with col1:
        spring_type = st.radio("板簧类型", ["卷耳片", "简单直片"], horizontal=True)
        if spring_type == "卷耳片":
            D = st.number_input("弦长半长 D (mm)", value=560.07, format="%.4f")
            H = st.number_input("自由弧高 H (mm)", value=108.0, format="%.4f")
            r = st.number_input("卷耳内半径 r (mm)", value=18.5, format="%.4f")
            t = st.number_input("片厚 t (mm)", value=10.0, format="%.4f")
        else:
            D = st.number_input("弦长半长 D (mm)", value=624.79, format="%.4f")
            H = st.number_input("自由弧高 H (mm)", value=59.0, format="%.4f")
            r = 0.0
            t = st.number_input("片厚 t (mm)", value=16.0, format="%.4f")

    with col2:
        mode = st.radio("计算模式", ["正向计算", "单变量反算"], horizontal=True)
        if mode == "单变量反算":
            target_var = st.selectbox("目标变量", ["曲率半径 R", "夹角 α (°)", "伸直半长 s", "伸直全长 2s", "弦长全长 2D"])
            target_val = st.number_input("目标值", value=0.0, format="%.6f")
            solve_var = st.selectbox("求解变量", ["D", "H", "r", "t"])
            solve_bounds = st.slider("求解范围", 0.01, 50000.0, (0.01, 10000.0))

    if st.button("计算", type="primary"):
        if mode == "正向计算":
            try:
                result = model1_forward(D, H, r, t)
                st.success("计算完成")
                df = pd.DataFrame(list(result.items()), columns=["参数", "值"])
                st.dataframe(df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"计算错误: {e}")
        else:
            params = {"D": D, "H": H, "r": r, "t": t}
            var_map = {"D": "D", "H": "H", "r": "r", "t": "t"}
            sol, result = solve_single_variable(
                model1_forward, params, var_map[solve_var],
                target_var, target_val, bounds=solve_bounds
            )
            if sol is not None:
                st.success(f"求解完成: {solve_var} = {sol:.6f}")
                df = pd.DataFrame(list(result.items()), columns=["参数", "值"])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.error("求解失败，请调整求解范围或检查参数")


# ------ 模型2 UI ------
def ui_model2():
    st.header("模型2: 非对称板簧弧高")

    col1, col2 = st.columns(2)
    with col1:
        total_straight = st.number_input("伸直全长 (mm)", value=1513.0, format="%.2f")
        center_arc = st.number_input("中心弧高 (mm)", value=138.0, format="%.2f")
        flat_len = st.number_input("中间平直段长 (mm)", value=200.0, format="%.2f")
    with col2:
        short_straight = st.number_input("短端伸直长 (mm)", value=695.0, format="%.2f")
        short_dia = st.number_input("短端卷耳孔径 (mm)", value=53.0, format="%.2f")
        long_dia = st.number_input("长端卷耳孔径 (mm)", value=53.0, format="%.2f")

    mode = st.radio("计算模式", ["正向计算", "单变量反算"], horizontal=True)

    if mode == "单变量反算":
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            target_var = st.selectbox("目标变量", ["R (参考)", "弧高H (短端)", "弧高H (长端)", "长端伸直长"])
        with col_b:
            target_val = st.number_input("目标值", value=0.0, format="%.6f")
        with col_c:
            solve_var = st.selectbox("求解变量", [
                "total_straight", "center_arc", "flat_len",
                "short_straight", "short_dia", "long_dia"
            ], format_func=lambda x: {
                "total_straight": "伸直全长",
                "center_arc": "中心弧高",
                "flat_len": "平直段长",
                "short_straight": "短端伸直长",
                "short_dia": "短端孔径",
                "long_dia": "长端孔径",
            }[x])
        solve_bounds = st.slider("求解范围", 0.01, 50000.0, (0.01, 10000.0))

    if st.button("计算", type="primary"):
        if mode == "正向计算":
            try:
                result = model2_forward(total_straight, center_arc, flat_len,
                                        short_straight, short_dia, long_dia)
                st.success("计算完成")
                df = pd.DataFrame(list(result.items()), columns=["参数", "值"])
                st.dataframe(df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"计算错误: {e}")
        else:
            params = {
                "total_straight": total_straight, "center_arc": center_arc,
                "flat_len": flat_len, "short_straight": short_straight,
                "short_dia": short_dia, "long_dia": long_dia,
            }
            sol, result = solve_single_variable(
                model2_forward, params, solve_var,
                target_var, target_val, bounds=solve_bounds
            )
            if sol is not None:
                label = {
                    "total_straight": "伸直全长", "center_arc": "中心弧高",
                    "flat_len": "平直段长", "short_straight": "短端伸直长",
                    "short_dia": "短端孔径", "long_dia": "长端孔径",
                }[solve_var]
                st.success(f"求解完成: {label} = {sol:.6f}")
                df = pd.DataFrame(list(result.items()), columns=["参数", "值"])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.error("求解失败，请调整求解范围或检查参数")


# ------ 模型3 UI ------
def ui_model3():
    st.header("模型3: 圆弧多片弧高计算")

    variant = st.radio("计算变体", ["标准 (无平直段)", "含弧长与平直段 (Sheet1(7)变体)"], horizontal=True)

    num_leaves = st.number_input("板簧片数", min_value=1, max_value=14, value=5, step=1)

    if variant.startswith("含"):
        eye_radius = st.number_input("卷耳内半径 (mm)", value=22.5, format="%.2f")
        cols_def = {
            "弧长 B_arc": [1296.0] + [1296.0, 966.0, 711.0, 485.0] + [500.0] * 9,
            "平直段 flat": [0.0] * 14,
            "第1片喷丸弧高 F1": [141.5] + [0.0] * 13,
            "间隙 G": [0.0, 7.5, 8.2, 3.7, 1.5] + [1.0] * 9,
            "厚度 K": [11.0] * 5 + [11.0] * 9,
            "喷丸系数 L": [0.0005] * 14,
        }
    else:
        cols_def = {
            "伸直长 B": [1800.0, 1800.0, 1820.0, 1620.0, 1352.0] + [1000.0] * 9,
            "第1片喷丸弧高 F1": [106.0] + [0.0] * 13,
            "间隙 G": [0.0, 7.0, 6.0, 5.0, 4.0] + [2.0] * 9,
            "厚度 K": [14.0] * 14,
            "喷丸系数 L": [0.0005] * 14,
        }

    # 端垫弧高
    add_tip_col = False
    if not variant.startswith("含"):
        add_tip_col = st.checkbox("含端垫修正 (加端垫后弧高)", value=False)
        if add_tip_col:
            cols_def["端垫 S"] = [0.0, 3.0] + [0.0] * 12

    # 构建编辑表格
    edit_data = {}
    for k, v in cols_def.items():
        edit_data[k] = v[:num_leaves]
    df_input = pd.DataFrame(edit_data, index=[f"第{i+1}片" for i in range(num_leaves)])
    edited = st.data_editor(df_input, use_container_width=True, num_rows="fixed")

    if st.button("计算", type="primary"):
        try:
            data = []
            for i in range(num_leaves):
                row = {}
                if variant.startswith("含"):
                    row["B"] = edited.iloc[i]["弧长 B_arc"]
                    row["arc_len"] = edited.iloc[i]["弧长 B_arc"]
                    row["flat_seg"] = edited.iloc[i]["平直段 flat"]
                else:
                    row["B"] = edited.iloc[i]["伸直长 B"]
                row["F1"] = edited.iloc[i]["第1片喷丸弧高 F1"]
                row["G"] = edited.iloc[i]["间隙 G"]
                row["K"] = edited.iloc[i]["厚度 K"]
                row["L"] = edited.iloc[i]["喷丸系数 L"]
                data.append(row)

            if variant.startswith("含"):
                results, summary = model3_with_eye(data, eye_radius)
            else:
                results, summary = model3_forward(data, variant="standard")

            # 端垫修正
            if add_tip_col and not variant.startswith("含"):
                sum_H_tip = 0
                for i, r in enumerate(results):
                    tip_s = edited.iloc[i].get("端垫 S", 0)
                    tip_arc = r["喷丸后弧高 F"] + tip_s
                    r["加端垫弧高"] = tip_arc
                    sum_H_tip += tip_arc / r["伸直长 B"]
                B1 = results[0]["伸直长 B"]
                summary["总成弧高 (加端垫)"] = B1 ** 2 * sum_H_tip / summary["Σ(B)"]

            st.success("计算完成")
            st.subheader("逐片结果")
            df_out = pd.DataFrame(results)
            st.dataframe(df_out, use_container_width=True, hide_index=True)

            st.subheader("总成汇总")
            df_sum = pd.DataFrame(list(summary.items()), columns=["参数", "值"])
            st.dataframe(df_sum, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"计算错误: {e}")


# ------ 模型4 UI ------
def ui_model4():
    st.header("模型4: 卷耳展开/下料长度")

    sub = st.radio("卷耳类型", [
        "4a: 简单卷耳 (3/4圈)",
        "4a-2: 1/4包耳",
        "4b: 带圆弧过渡卷耳",
        "4c: 二片包耳",
        "4d: 三片包耳",
    ])

    if sub.startswith("4a:"):
        col1, col2 = st.columns(2)
        with col1:
            D = st.number_input("卷耳孔径 D (mm)", value=32.5, format="%.2f")
            L = st.number_input("板身长度 L (mm)", value=600.0, format="%.2f")
        with col2:
            h = st.number_input("板簧厚度 h (mm)", value=9.0, format="%.2f")
            both = st.checkbox("双端卷耳", value=True)
            width = st.number_input("料宽 (mm)", value=80.0, format="%.2f")

        if st.button("计算", type="primary"):
            result = model4a_simple_eye(D, L, h, both)
            result["重量 (kg)"] = calc_weight(width, h, result["断料全长"] if both else result["断料半长"])
            df = pd.DataFrame(list(result.items()), columns=["参数", "值"])
            st.dataframe(df, use_container_width=True, hide_index=True)

    elif sub.startswith("4a-2"):
        col1, col2 = st.columns(2)
        with col1:
            D = st.number_input("卷耳孔径 D (mm)", value=37.0, format="%.2f")
            L = st.number_input("板身长度 L (mm)", value=577.0, format="%.2f")
        with col2:
            h = st.number_input("板簧厚度 h (mm)", value=10.0, format="%.2f")

        if st.button("计算", type="primary"):
            result = model4a_quarter(D, L, h)
            df = pd.DataFrame(list(result.items()), columns=["参数", "值"])
            st.dataframe(df, use_container_width=True, hide_index=True)

    elif sub.startswith("4b"):
        col1, col2 = st.columns(2)
        with col1:
            D = st.number_input("卷耳孔径 D (mm)", value=44.0, format="%.2f")
            L = st.number_input("板身长度 L (mm)", value=600.0, format="%.2f")
        with col2:
            h = st.number_input("板簧厚度 h (mm)", value=9.0, format="%.2f")
            R_arc = st.number_input("圆弧半径 R (mm)", value=50.0, format="%.2f")
            width = st.number_input("料宽 (mm)", value=90.0, format="%.2f")

        if st.button("计算", type="primary"):
            result = model4b_arc_eye(D, L, h, R_arc)
            result["重量 (kg)"] = calc_weight(width, h, result["断料全长"])
            df = pd.DataFrame(list(result.items()), columns=["参数", "值"])
            st.dataframe(df, use_container_width=True, hide_index=True)

    elif sub.startswith("4c"):
        col1, col2 = st.columns(2)
        with col1:
            D = st.number_input("卷耳孔径 D (mm)", value=44.0, format="%.2f")
            L = st.number_input("板身长度 L (mm)", value=600.0, format="%.2f")
            h = st.number_input("板簧厚度 h (mm)", value=9.0, format="%.2f")
        with col2:
            h1 = st.number_input("芯部高度 h1 (mm)", value=4.5, format="%.2f")
            H_open = st.number_input("开口高度 H (mm)", value=30.0, format="%.2f")
            r_arc = st.number_input("圆弧半径 r (mm)", value=25.0, format="%.2f")
            width = st.number_input("料宽 (mm)", value=90.0, format="%.2f")

        if st.button("计算", type="primary"):
            result = model4c_wrap2(D, L, h, h1, H_open, r_arc)
            result["重量 (kg)"] = calc_weight(width, h, result["展开全长"])
            df = pd.DataFrame(list(result.items()), columns=["参数", "值"])
            st.dataframe(df, use_container_width=True, hide_index=True)

    elif sub.startswith("4d"):
        col1, col2 = st.columns(2)
        with col1:
            D = st.number_input("卷耳孔径 D (mm)", value=44.0, format="%.2f")
            L = st.number_input("板身长度 L (mm)", value=600.0, format="%.2f")
            h = st.number_input("板簧厚度 h (mm)", value=9.0, format="%.2f")
        with col2:
            h1 = st.number_input("芯部高度 h1 (mm)", value=13.5, format="%.2f")
            H_open = st.number_input("开口高度 H (mm)", value=40.0, format="%.2f")
            r_arc = st.number_input("圆弧半径 r (mm)", value=25.0, format="%.2f")
            extra_h = st.number_input("额外R增量 (mm)", value=0.0, format="%.2f",
                                      help="在二片R基础上的额外增量")

        if st.button("计算", type="primary"):
            # 二片包耳R基础值
            R2 = (D + 2 * h + 4) / 2
            actual_extra = h + 2 if extra_h == 0 else extra_h
            result = model4d_wrap3(D, L, h, h1, H_open, r_arc, extra_h=actual_extra)
            df = pd.DataFrame(list(result.items()), columns=["参数", "值"])
            st.dataframe(df, use_container_width=True, hide_index=True)


# ------ 模型5 UI ------
def ui_model5():
    st.header("模型5: 变截面总成弧高")

    num_leaves = st.number_input("板簧片数", min_value=1, max_value=14, value=3, step=1)
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        shot_coeff = st.number_input("喷丸系数", value=0.0005, format="%.6f")
    with col_s2:
        eye_dia = st.number_input("卷耳孔径 (mm)", value=30.0, format="%.2f")

    # 默认数据 (Sheet1(不动) 的示例)
    defaults = {
        "伸直长 B": [1200.0] * 3 + [1200.0] * 11,
        "平直段 C": [160.0] * 3 + [160.0] * 11,
        "第1片等长弧高 E1": [95.0] + [0.0] * 13,
        "间隙 F": [0.0, 13.5, 11.0] + [10.0] * 11,
        "板厚 G": [16.0] * 14,
        "端部厚 H": [10.0, 9.0, 9.0] + [9.0] * 11,
        "降噪片 I": [0.0] * 14,
        "垫片 J": [0.0, 1.0, 1.0] + [1.0] * 11,
    }

    edit_data = {}
    for k, v in defaults.items():
        edit_data[k] = v[:num_leaves]
    df_input = pd.DataFrame(edit_data, index=[f"第{i+1}片" for i in range(num_leaves)])
    edited = st.data_editor(df_input, use_container_width=True, num_rows="fixed")

    # 目标总成弧高（可选反算）
    st.markdown("---")
    mode = st.radio("计算模式", ["正向计算", "反算第1片弧高"], horizontal=True)
    if mode == "反算第1片弧高":
        target_assembly = st.number_input("目标总成弧高 (带卷耳, mm)", value=125.0, format="%.4f")

    if st.button("计算", type="primary"):
        try:
            data = []
            for i in range(num_leaves):
                row = {
                    "B": edited.iloc[i]["伸直长 B"],
                    "C": edited.iloc[i]["平直段 C"],
                    "E1": edited.iloc[i]["第1片等长弧高 E1"],
                    "F_gap": edited.iloc[i]["间隙 F"],
                    "G": edited.iloc[i]["板厚 G"],
                    "H_end": edited.iloc[i]["端部厚 H"],
                    "I_noise": edited.iloc[i]["降噪片 I"],
                    "J_shim": edited.iloc[i]["垫片 J"],
                }
                data.append(row)

            if mode == "正向计算":
                results, summary = model5_forward(data, shot_coeff, eye_dia)
            else:
                # 反算: 调整 E1 使总成弧高匹配目标
                def obj(e1_val):
                    data[0]["E1"] = e1_val
                    _, s = model5_forward(data, shot_coeff, eye_dia)
                    return s["样板总成弧高+卷耳"] - target_assembly

                try:
                    e1_sol = brentq(obj, 0.01, 5000, xtol=1e-8)
                    data[0]["E1"] = e1_sol
                    st.info(f"反算得到第1片等长弧高 E1 = {e1_sol:.6f} mm")
                except ValueError:
                    st.error("反算失败，请调整目标值")
                    return
                results, summary = model5_forward(data, shot_coeff, eye_dia)

            st.success("计算完成")
            st.subheader("逐片结果")
            df_out = pd.DataFrame(results)
            st.dataframe(df_out, use_container_width=True, hide_index=True)

            st.subheader("总成汇总")
            df_sum = pd.DataFrame(list(summary.items()), columns=["参数", "值"])
            st.dataframe(df_sum, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"计算错误: {e}")


if __name__ == "__main__":
    main()
