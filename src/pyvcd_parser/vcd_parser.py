import dataclasses

import vcd
from vcd.reader import TokenKind, ScopeDecl, VarDecl
from vcd.common import Timescale, ScopeType, VarType
from typing import Optional, Dict, List, BinaryIO
from dataclasses import dataclass, field
from bisect import bisect_left

import json


@dataclass
class SignalChange:
    time: int
    value: str


@dataclass
class SignalTrace:
    identifier: str
    type: VarType
    size: int

    changes: List[SignalChange] = field(default_factory=list)

    def match(self, spec: dict) -> bool:
        match = True

        if "identifier" in spec:
            match = match and (spec["identifier"] == self.identifier)

        if "size" in spec:
            match = match and (spec["size"] == self.size)

        if "type" in spec:
            match = match and (spec["type"] == self.type.value)

        return match

    def get_value_at_time(self, time: int):
        index = bisect_left(self.changes, time, key=lambda x: x.time)
        signal_value = self.changes[index - 1].value
        return signal_value


@dataclass
class Scope:
    identifier: str
    type: ScopeType
    children: Dict[str, "Scope"] = field(default_factory=dict)
    signals: Dict[str, SignalTrace] = field(default_factory=dict)

    def match(self, spec: dict):
        match = True

        if "identifier" in spec:
            match = match and (spec["identifier"] == self.identifier)

        if "type" in spec:
            match = match and (spec["type"] == self.type.value)

        if "signals" in spec:
            for name, signal in spec["signals"].items():
                match = match and ((name in self.signals) and (self.signals[name].match(signal)))

        return match

    def match_children(self, spec) -> Optional["Scope"]:
        for child in self.children.values():
            if child.match(spec):
                return child

        return None


def parse_vcd(file: BinaryIO) -> Scope:
    tokens = vcd.reader.tokenize(file)

    date: Optional[str] = None
    version: Optional[str] = None
    timescale: Optional[Timescale] = None

    current_time = 0

    root_scope = Scope("root", ScopeType.module)
    scope_stack = [root_scope]

    id_to_signal_map: Dict[str, List[SignalTrace]] = dict()

    for token in tokens:
        # print(token)
        if token.kind is TokenKind.DATE:
            date = token.data
        elif token.kind is TokenKind.VERSION:
            version = token.data
        elif token.kind is TokenKind.TIMESCALE:
            timescale = token.data
        elif token.kind is TokenKind.SCOPE:
            scope_decl: ScopeDecl = token.data
            new_scope = Scope(scope_decl.ident, scope_decl.type_)

            scope_stack[-1].children[scope_decl.ident] = new_scope
            scope_stack.append(new_scope)
        elif token.kind is TokenKind.UPSCOPE:
            del scope_stack[-1]
        elif token.kind is TokenKind.VAR:
            var_decal: VarDecl = token.data

            new_signal = SignalTrace(var_decal.reference, var_decal.type_, var_decal.size)

            if var_decal.id_code not in id_to_signal_map:
                id_to_signal_map[var_decal.id_code] = list()

            id_to_signal_map[var_decal.id_code].append(new_signal)

            scope_stack[-1].signals[var_decal.reference] = new_signal
        elif token.kind is TokenKind.CHANGE_TIME:
            current_time = token.data
        elif token.kind is TokenKind.CHANGE_SCALAR or token.kind is TokenKind.CHANGE_VECTOR:
            value = token.data.value
            id_code = token.data.id_code

            if id_code in id_to_signal_map:
                for signal in id_to_signal_map[id_code]:
                    if isinstance(value, int):
                        value = f"{value:b}"
                        # value = value.rjust(signal.size, "0")
                    new_signal_change = SignalChange(time=current_time, value=value)
                    signal.changes.append(new_signal_change)

    return root_scope


def main():
    with open("hw4_dump.vcd", "rb") as infile:
        root = parse_vcd(infile)
        print(root)
        test_bench = root.children["testbench"]
        dp = test_bench.children["dp"]
        print(dp)

        with open("module_db2.json") as module_db_file:
            module_db = json.load(module_db_file)

        for module_name, spec in module_db.items():
            # print(spec)
            print(f"{module_name}: {dp.match_children(spec)}")


if __name__ == "__main__":
    main()
