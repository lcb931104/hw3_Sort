import random
import multiprocessing
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

# 選擇排序(Selection sort)
def SelectSort(Array, progress_callback=None):
    n = len(Array)

    # 初始化計算進度條
    if progress_callback:
        progress_callback(0)

    # 從陣列左到右依序選每個數字
    for i in range(len(Array)):
        min_index = i
        
        # 找陣列中被選數字的右邊裡最小的數字
        for j in range(i+1, len(Array)):

            # 如果最小數字 < 被選數字，兩個就交換
            if Array[j] < Array[min_index]:
                min_index = j

        Array[i], Array[min_index] = Array[min_index], Array[i]

        # 回報演算法進度
        if progress_callback:
            progress_callback(((i + 1) / n) * 100)

    return Array

# 泡泡排序(Bubble sort)
def BubbleSort(Array, progress_callback=None):

    # 初始化計算進度條
    n = len(Array)
    total_steps = n * (n - 1) // 2
    done_steps = 0
    update_interval = max(1, total_steps // 1000)

    if progress_callback:
        progress_callback(0)

    for i in range(n-1):

        # 陣列中每個數字跟右邊那個比大小，左 > 右的話交換
        for j in range(i+1, n):
            if Array[i] > Array[j]:
                Array[i],Array[j] = Array[j],Array[i]

            # 回報演算法進度
            done_steps += 1
            if progress_callback and done_steps % update_interval == 0:
                progress_callback((done_steps / total_steps) * 100)

    if progress_callback:
        progress_callback(100)

    return Array

# 快速排序(Quick sort)
def QuickSort(Array,Start,End, progress_callback=None, progress_state=None):

    # 初始化計算進度條
    if progress_callback and progress_state is None:
        progress_state = {"total": len(Array), "done": 0}
        progress_callback(0)

    if Start >= End:
        if progress_callback and progress_state and 0 <= Start < len(Array):
            progress_state["done"] += 1
            progress_callback((progress_state["done"] / progress_state["total"]) * 100)
        return Array

    # 設定好左右指標以及pivot
    pivot = Array[Start]
    left = Start
    right = End

    # 重複直到左右指標重疊
    while left < right:

        # 右指標走到小於pivot
        while Array[right] >= pivot and right > left:
            right -= 1

        # 左指標走到大於pivot
        while Array[left] <= pivot and right > left:
            left += 1
        
        # 兩個交換
        Array[left], Array[right] = Array[right], Array[left]
    
    # 指標重疊時，pivot移到右指標位置
    Array[Start], Array[right] = Array[right], Array[Start]

    # 回報演算法進度
    if progress_callback and progress_state:
        progress_state["done"] += 1
        progress_callback((progress_state["done"] / progress_state["total"]) * 100)

    # 遞迴將陣列分兩部分並分別做一樣的事
    QuickSort(Array,Start,right-1, progress_callback, progress_state)
    QuickSort(Array,right+1,End, progress_callback, progress_state)

    if progress_callback and progress_state["done"] >= progress_state["total"]:
        progress_callback(100)

    return Array


SORT_ALGORITHMS = (
    ("Selection Sort", "SelectSort"),
    ("Bubble Sort", "BubbleSort"),
    ("Quick Sort", "QuickSort"),
)

# 定義三個演算法
def run_sort(function_name, data, progress_callback=None):
    if function_name == "SelectSort":
        return SelectSort(data, progress_callback)
    if function_name == "BubbleSort":
        return BubbleSort(data, progress_callback)
    if function_name == "QuickSort":
        return QuickSort(data, 0, len(data) - 1, progress_callback)
    raise ValueError(f"Unknown sort function: {function_name}")

# 在 GUI 外開一個 process 執行演算法，並把結果傳給 GUI
def sort_worker(function_name, data, output_queue):
    last_progress = -1
    expected = sorted(data)

    def progress_callback(percent):
        nonlocal last_progress
        percent = max(0, min(100, percent))
        rounded = round(percent, 1)
        if rounded >= 100 or rounded - last_progress >= 0.1:
            last_progress = rounded
            output_queue.put(("progress", rounded, None))

    try:
        started_at = time.perf_counter()
        sorted_data = run_sort(function_name, data, progress_callback)
        seconds = time.perf_counter() - started_at
        output_queue.put(("progress", 100, None))
        output_queue.put(("ok", seconds, sorted_data == expected))
    except Exception as exc:
        output_queue.put(("error", str(exc), None))

# 啟動演算法
def benchmark_one(name, function_name, numbers, stop_event, active_processes, process_lock, progress_callback):
    output_queue = multiprocessing.Queue()
    process = multiprocessing.Process(
        target=sort_worker,
        args=(function_name, numbers.copy(), output_queue),
    )

    process.start()
    with process_lock:
        active_processes[name] = process

    try:
        final_result = None

        while process.is_alive():
            try:
                while True:
                    status, value, payload = output_queue.get_nowait()
                    if status == "progress":
                        progress_callback(value)
                    else:
                        final_result = (status, value, payload)
            except queue.Empty:
                pass

            if final_result:
                process.join(timeout=1)
                return final_result

            if stop_event.is_set():
                process.terminate()
                process.join()
                return ("stopped", "已強制停止", None)

            process.join(0.1)

        try:
            while True:
                status, value, payload = output_queue.get_nowait()
                if status == "progress":
                    progress_callback(value)
                else:
                    final_result = (status, value, payload)
        except queue.Empty:
            pass

        if final_result:
            return final_result

        if stop_event.is_set():
            return ("stopped", "已強制停止", None)

        try:
            while True:
                status, value, payload = output_queue.get(timeout=1)
                if status == "progress":
                    progress_callback(value)
                else:
                    return (status, value, payload)
        except queue.Empty:
            return ("error", "排序程序沒有回傳結果。", None)
    finally:
        with process_lock:
            active_processes.pop(name, None)

# GUI 介面
class SortBenchmarkGUI:

    # GUI 初始設定
    def __init__(self, root):
        self.root = root
        self.root.title("排序演算法效能比較")
        self.root.geometry("620x470")
        self.root.minsize(580, 430)
        self.is_running = False

        self.n_var = tk.StringVar(value="1000")
        self.status_var = tk.StringVar(value="請設定 N 後開始測試")
        self.fastest_var = tk.StringVar(value="最快：尚未測試")
        self.elapsed_var = tk.StringVar(value="總耗時：0.000000 秒")
        self.progress_bars = {}
        self.progress_vars = {}
        self.percent_vars = {}
        self.completed_count = 0
        self.stop_event = threading.Event()
        self.active_processes = {}
        self.process_lock = threading.Lock()

        self._build_ui()

    # 設定 GUI 要有的功能
    def _build_ui(self):
        main = ttk.Frame(self.root, padding=18)
        main.pack(fill="both", expand=True)

        controls = ttk.Frame(main)
        controls.pack(fill="x")

        ttk.Label(controls, text="N：").pack(side="left")
        self.n_entry = ttk.Spinbox(
            controls,
            from_=1,
            to=50000,
            increment=100,
            textvariable=self.n_var,
            width=12,
        )
        self.n_entry.pack(side="left", padx=(4, 12))

        self.run_button = ttk.Button(controls, text="開始測試", command=self.start_benchmark)
        self.run_button.pack(side="left")
        self.stop_button = ttk.Button(
            controls,
            text="強制停止",
            command=self.stop_benchmark,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=(8, 0))

        ttk.Label(
            main,
            textvariable=self.status_var,
            anchor="w",
        ).pack(fill="x", pady=(18, 6))

        progress_area = ttk.Frame(main)
        progress_area.pack(fill="x", pady=(4, 10))

        for name, _ in SORT_ALGORITHMS:
            row = ttk.Frame(progress_area)
            row.pack(fill="x", pady=4)

            ttk.Label(row, text=f"{name}:", width=16, anchor="w").pack(side="left")

            progress_var = tk.DoubleVar(value=0)
            percent_var = tk.StringVar(value="0%")
            bar = ttk.Progressbar(
                row,
                mode="determinate",
                maximum=100,
                variable=progress_var,
            )
            bar.pack(side="left", fill="x", expand=True, padx=(6, 10))
            ttk.Label(row, textvariable=percent_var, width=5, anchor="e").pack(side="left")

            self.progress_bars[name] = bar
            self.progress_vars[name] = progress_var
            self.percent_vars[name] = percent_var

        columns = ("algorithm", "seconds", "rank")
        self.result_tree = ttk.Treeview(main, columns=columns, show="headings", height=6)
        self.result_tree.heading("algorithm", text="排序演算法")
        self.result_tree.heading("seconds", text="執行秒數")
        self.result_tree.heading("rank", text="名次")
        self.result_tree.column("algorithm", width=180, anchor="center")
        self.result_tree.column("seconds", width=160, anchor="center")
        self.result_tree.column("rank", width=80, anchor="center")
        self.result_tree.pack(fill="both", expand=True, pady=(16, 10))
        self.result_tree.tag_configure("fastest", background="#d8f5dd")

        ttk.Label(main, textvariable=self.fastest_var, anchor="w").pack(fill="x", pady=(0, 4))
        ttk.Label(main, textvariable=self.elapsed_var, anchor="w").pack(fill="x", pady=(0, 4))

    # 開始執行
    def start_benchmark(self):
        if self.is_running:
            return

        try:
            n = int(self.n_var.get())
        except ValueError:
            messagebox.showerror("輸入錯誤", "N 必須是整數。")
            return

        if n <= 0:
            messagebox.showerror("輸入錯誤", "N 必須大於 0。")
            return

        self.is_running = True
        self.stop_event.clear()
        self.run_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.completed_count = 0
        for name, _ in SORT_ALGORITHMS:
            self._set_algorithm_progress(name, 0)
        self.fastest_var.set("最快：測試中")
        self.elapsed_var.set("總耗時：0.000000 秒")
        self.status_var.set("正在產生不重複隨機數字...")
        self._clear_results()

        worker = threading.Thread(target=self._run_benchmark, args=(n,), daemon=True)
        worker.start()

    # 強制停止
    def stop_benchmark(self):
        if not self.is_running:
            return

        self.stop_event.set()
        self.status_var.set("正在強制停止...")
        self.stop_button.config(state="disabled")

    # 確保關掉 app
    def close_app(self):
        self.stop_event.set()

        with self.process_lock:
            processes = list(self.active_processes.values())

        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)

        self.root.destroy()

    # 三個演算法跑的當下，GUI 要做什麼
    def _run_benchmark(self, n):
        try:
            upper_bound = max(n * 10, n + 1)
            numbers = random.sample(range(1, upper_bound + 1), n)
            results = []
            results_lock = threading.Lock()
            total_start = time.perf_counter()

            self.root.after(0, self.status_var.set, "三個演算法執行中...")

            threads = []
            for name, function_name in SORT_ALGORITHMS:
                self.root.after(0, self._mark_algorithm_started, name)
                worker = threading.Thread(
                    target=self._run_algorithm,
                    args=(name, function_name, numbers, results, results_lock),
                    daemon=True,
                )
                threads.append(worker)
                worker.start()

            for worker in threads:
                worker.join()

            total_seconds = time.perf_counter() - total_start
            self.root.after(0, self._show_results, results, total_seconds)
        except Exception as exc:
            self.root.after(0, self._show_error, str(exc))

    # call 三個演算法跑
    def _run_algorithm(self, name, function_name, numbers, results, results_lock):
        status, seconds_or_message, is_correct = benchmark_one(
            name,
            function_name,
            numbers,
            self.stop_event,
            self.active_processes,
            self.process_lock,
            lambda percent: self.root.after(0, self._set_algorithm_progress, name, percent),
        )

        if status == "ok" and is_correct:
            result = (name, seconds_or_message, "完成")
        elif status == "stopped":
            result = (name, None, "已強制停止")
        elif status == "ok":
            result = (name, None, "排序結果不正確")
        else:
            result = (name, None, str(seconds_or_message))

        with results_lock:
            results.append(result)

        self.root.after(0, self._mark_algorithm_finished, name, status)

    # 演算法開始訊號
    def _mark_algorithm_started(self, name):
        self._set_algorithm_progress(name, 0)

    # 演算法結束訊號
    def _mark_algorithm_finished(self, name, status):
        if status == "stopped":
            self.percent_vars[name].set("停止")
        else:
            self._set_algorithm_progress(name, 100)
        self.completed_count += 1
        self.status_var.set(f"已完成 {self.completed_count}/{len(SORT_ALGORITHMS)} 個演算法")

    # 演算法跑的過程
    def _set_algorithm_progress(self, name, value):
        value = max(0, min(100, value))
        self.progress_vars[name].set(value)
        self.percent_vars[name].set(f"{int(value)}%")

    # 顯示結果
    def _show_results(self, results, total_seconds):
        order = {name: index for index, (name, _) in enumerate(SORT_ALGORITHMS)}
        successful = [(name, seconds) for name, seconds, _ in results if seconds is not None]

        self._clear_results()
        if successful:
            ranked = sorted(successful, key=lambda item: item[1])
            rank_by_name = {name: rank for rank, (name, _) in enumerate(ranked, start=1)}
            fastest_name, fastest_seconds = ranked[0]
        else:
            rank_by_name = {}
            fastest_name = None
            fastest_seconds = None

        results = sorted(results, key=lambda item: (rank_by_name.get(item[0], 999), order[item[0]]))

        for name, seconds, note in results:
            tags = ("fastest",) if name == fastest_name else ()
            seconds_text = f"{seconds:.6f}" if seconds is not None else note
            rank_text = rank_by_name.get(name, "-")
            self.result_tree.insert(
                "",
                "end",
                values=(name, seconds_text, rank_text),
                tags=tags,
            )

        if fastest_name is None:
            self.fastest_var.set("最快：沒有成功完成的演算法")
        else:
            self.fastest_var.set(f"最快：{fastest_name}，{fastest_seconds:.6f} 秒")
        self.elapsed_var.set(f"總耗時：{total_seconds:.6f} 秒")
        if self.stop_event.is_set():
            self.status_var.set("已強制停止")
        else:
            self.status_var.set("測試完成")
        self._finish_run()

    # 如果有錯時的程式
    def _show_error(self, message):
        self.status_var.set("測試中止")
        messagebox.showerror("測試失敗", message)
        self._finish_run()

    # 結束三個演算法的程式
    def _finish_run(self):
        self.is_running = False
        self.run_button.config(state="normal")
        self.stop_button.config(state="disabled")

    # 清除結果的程式
    def _clear_results(self):
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

# 初始化 APP
if __name__ == "__main__":
    multiprocessing.freeze_support()
    root = tk.Tk()
    app = SortBenchmarkGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.close_app)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.close_app()
