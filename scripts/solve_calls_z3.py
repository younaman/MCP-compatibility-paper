#!/usr/bin/env python3
import json
import glob
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
	from z3 import Solver, Bool, Int, String, And, Or, Not, Implies, Distinct, sat
except Exception as e:
	print("Z3 not available. Please install z3-solver: pip install z3-solver")
	raise

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"

@dataclass
class CallIR:
	file: str
	kind: str              # "func_call" | "method_call"
	name: Optional[str]    # may be None in lenient mode
	recv: Optional[str]    # only for method_call; may be None
	cond: str
	order: int
	line: int
	col: int

@dataclass
class DefIR:
	file: str
	kind: str
	name: Optional[str]
	params: Optional[str]
	order: int
	line: int
	col: int


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
	rows: List[Dict[str, Any]] = []
	with path.open("r", encoding="utf-8") as f:
		for line in f:
			line = line.strip()
			if not line:
				continue
			rows.append(json.loads(line))
	return rows


def read_calls_by_lang(lang: str) -> List[CallIR]:
	"""Read calls for a specific language/SDK."""
	calls: List[CallIR] = []
	fp = OUT_DIR / f"calls_{lang}.jsonl"
	if not fp.exists():
		print(f"Warning: {fp} not found")
		return calls
	
	for row in load_jsonl(fp):
		file_path = row.get("file")
		for ev in row.get("calls", []):
			calls.append(
				CallIR(
					file=file_path,
					kind=ev.get("kind"),
					name=ev.get("name"),
					recv=ev.get("recv"),
					cond=ev.get("cond", "true"),
					order=int(ev.get("order", 0)),
					line=int(ev.get("line", 0)),
					col=int(ev.get("col", 0)),
				)
			)
	return calls


def read_defs_by_lang(lang: str) -> List[DefIR]:
	"""Read definitions for a specific language/SDK."""
	defs: List[DefIR] = []
	fp = OUT_DIR / f"defs_{lang}.jsonl"
	if not fp.exists():
		print(f"Warning: {fp} not found")
		return defs
	
	for row in load_jsonl(fp):
		file_path = row.get("file")
		for d in row.get("definitions", []):
			defs.append(
				DefIR(
					file=file_path,
					kind=d.get("kind"),
					name=d.get("name"),
					params=d.get("params"),
					order=int(d.get("order", 0)),
					line=int(d.get("line", 0)),
					col=int(d.get("col", 0)),
				)
			)
	return defs


def get_available_langs() -> List[str]:
	"""Get list of available languages from calls_*.jsonl files."""
	langs = []
	for fp in glob.glob(str(OUT_DIR / "calls_*.jsonl")):
		# Extract language from filename, handling cases like calls_c_sharp.jsonl
		filename = Path(fp).stem  # Remove .jsonl extension
		if filename.startswith('calls_'):
			lang = filename[6:]  # Remove 'calls_' prefix
			langs.append(lang)
	return sorted(langs)


class IRModel:
	"""Z3 variables and constraints for calls/defs."""
	def __init__(self, calls: List[CallIR], defs: List[DefIR], mode: str = "lenient") -> None:
		self.solver = Solver()
		self.mode = mode  # "lenient" or "strict"
		self.calls = calls
		self.defs = defs
		self.v_names: List[String] = []
		self.v_recvs: List[String] = []
		self.v_orders: List[Int] = []
		self._build_vars()

	def _fresh_str(self, prefix: str) -> String:
		# Using order to stabilize symbol names
		return String(f"{prefix}")

	def _build_vars(self) -> None:
		for i, c in enumerate(self.calls):
			v_name = String(f"name_{i}")
			v_recv = String(f"recv_{i}")
			v_order = Int(f"order_{i}")
			self.v_names.append(v_name)
			self.v_recvs.append(v_recv)
			self.v_orders.append(v_order)

			# order always concrete
			self.solver.add(v_order == c.order)

			# name handling
			if c.name is None:
				if self.mode == "strict":
					# name must be non-empty string, but unknown
					pass  # leave unconstrained
				else:
					# lenient: allow arbitrary
					pass
			else:
				self.solver.add(v_name == c.name)

			# recv handling for method calls
			if c.kind == "method_call":
				if c.recv is None:
					# allow unknown receiver; no constraint
					pass
				else:
					self.solver.add(v_recv == c.recv)
			else:
				# for func_call, normalize to empty
				self.solver.add(v_recv == "")

	def add_rule_before(self, name_a: str, name_b: str, soft: bool = False) -> None:
		"""Constraint: any A must happen before any B (by order)."""
		for i, c_i in enumerate(self.calls):
			for j, c_j in enumerate(self.calls):
				# We only constrain when concrete names match; unknowns are ignored in this simple rule.
				cond_i = (self.v_names[i] == name_a) if c_i.name is not None else None
				cond_j = (self.v_names[j] == name_b) if c_j.name is not None else None
				if cond_i is not None and cond_j is not None:
					if not soft:
						self.solver.add(Implies(And(cond_i, cond_j), self.v_orders[i] < self.v_orders[j]))
					# soft 情况可以只打印 warning，不加约束

	def add_rule_after(self, name_a: str, name_b: str) -> None:
		"""Constraint: any A must happen after any B (by order)."""
		for i, c_i in enumerate(self.calls):
			for j, c_j in enumerate(self.calls):
				cond_i = (self.v_names[i] == name_a) if c_i.name is not None else None
				cond_j = (self.v_names[j] == name_b) if c_j.name is not None else None
				if cond_i is not None and cond_j is not None:
					self.solver.add(Implies(And(cond_i, cond_j), self.v_orders[i] > self.v_orders[j]))

	def add_rule_same_receiver(self, name_a: str, name_b: str) -> None:
		"""Constraint: if A and B happen, they must be on the same receiver."""
		for i, c_i in enumerate(self.calls):
			for j, c_j in enumerate(self.calls):
				cond_i = (self.v_names[i] == name_a) if c_i.name is not None else None
				cond_j = (self.v_names[j] == name_b) if c_j.name is not None else None
				if cond_i is not None and cond_j is not None:
					self.solver.add(Implies(And(cond_i, cond_j), self.v_recvs[i] == self.v_recvs[j]))

	def add_rule_different_receiver(self, name_a: str, name_b: str) -> None:
		"""Constraint: if A and B happen, they must be on different receivers."""
		for i, c_i in enumerate(self.calls):
			for j, c_j in enumerate(self.calls):
				cond_i = (self.v_names[i] == name_a) if c_i.name is not None else None
				cond_j = (self.v_names[j] == name_b) if c_j.name is not None else None
				if cond_i is not None and cond_j is not None:
					self.solver.add(Implies(And(cond_i, cond_j), self.v_recvs[i] != self.v_recvs[j]))

	def add_rule_must_exist(self, name: str) -> None:
		"""Constraint: at least one call with this name must exist."""
		conditions = []
		for i, c in enumerate(self.calls):
			if c.name is not None:
				conditions.append(self.v_names[i] == name)
		if conditions:
			self.solver.add(Or(conditions))

	def add_rule_must_not_exist(self, name: str) -> None:
		"""Constraint: no call with this name should exist."""
		for i, c in enumerate(self.calls):
			if c.name is not None:
				self.solver.add(self.v_names[i] != name)

	def add_rule_exists(self, name: str, soft: bool = False) -> None:
		"""Constraint: at least one call with this name must exist."""
		found = [self.v_names[i] == name for i, c in enumerate(self.calls) if c.name is not None]
		if found:
			self.solver.add(Or(*found))  # 至少一个
		elif not soft:
			self.solver.add(False)       # 硬违反

	def add_rule_forbid(self, name: str, soft: bool = False) -> None:
		"""Constraint: no call with this name should exist."""
		forbids = [self.v_names[i] == name for i, c in enumerate(self.calls) if c.name is not None]
		if forbids:
			if not soft:
				self.solver.add(Not(Or(*forbids)))  # 禁止出现
			# soft 情况可以只打印 warning，不加约束

	def add_rule_at_most_once(self, name: str, soft: bool = False) -> None:
		"""Constraint: call with this name should appear at most once."""
		idx = [i for i, c in enumerate(self.calls) if c.name == name]
		if len(idx) > 1:
			if not soft:
				# 硬约束：这些 indices 不能全相等
				self.solver.add(Distinct(*[self.v_orders[i] for i in idx]))
			# soft 情况可以只打印 warning，不加约束

	def check(self) -> Tuple[bool, Optional[Any]]:
		res = self.solver.check()
		if res == sat:
			return True, self.solver.model()
		return False, None


def analyze_lang(lang: str, max_calls: int = 100) -> None:
	"""Analyze a specific language/SDK."""
	print(f"\n=== Analyzing {lang.upper()} SDK ===")
	
	calls = read_calls_by_lang(lang)
	defs = read_defs_by_lang(lang)
	print(f"Loaded {len(calls)} calls, {len(defs)} definitions")
	
	if not calls:
		print(f"No calls found for {lang}")
		return
	
	# Limit data for testing
	calls = calls[:max_calls]
	defs = defs[:50]
	print(f"Testing with {len(calls)} calls, {len(defs)} definitions")
	
	# For rule checking, we need to check ALL calls, not just the limited subset
	all_calls = read_calls_by_lang(lang)

	model = IRModel(calls, defs, mode="lenient")
	print("Built Z3 model")
	
	# Test rule: if 'list_tools' exists, then some notification should exist
	# This is a simplified version of the MCP rule about tool list changes
	has_list_tools = any(c.name == "list_tools" for c in all_calls)
	has_notification = any("notification" in (c.name or "") or "notify" in (c.name or "") for c in all_calls)
	
	if has_list_tools and not has_notification:
		print("VIOLATION: list_tools found but no notification function found")
		# Add constraint that should make it UNSAT
		model.add_rule_exists("send_tool_list_changed_notification")
	else:
		print("OK: Either no list_tools or notification function exists")
	
	# Test: Add a constraint that should always fail to verify UNSAT works
	# This tests that the Z3 solver can actually return UNSAT
	print("Testing UNSAT capability...")
	model.add_rule_exists("this_function_does_not_exist_anywhere")
	
	print("Added constraints")
	
	ok, m = model.check()
	print("SAT" if ok else "UNSAT")
	if ok:
		# Print a small projection for first 10 calls
		for i, c in enumerate(calls[:10]):
			print(f"#{i+1:02d} {c.kind} name={c.name} recv={c.recv} order={c.order}")


def main() -> None:
	"""Analyze each language/SDK separately."""
	available_langs = get_available_langs()
	print(f"Available languages: {available_langs}")
	
	# Analyze each language separately
	for lang in available_langs:
		analyze_lang(lang, max_calls=50)  # Smaller limit for testing

if __name__ == "__main__":
	main()


