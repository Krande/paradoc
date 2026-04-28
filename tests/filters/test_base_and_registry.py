"""Filter base class, @attr decorator, and registry behavior."""

import pytest

from paradoc.filters import (
    Filter,
    FilterRegistry,
    ScalarValue,
    TableView,
    attr,
)
from paradoc.filters.cache import AttrCache, _hash_args


class _SimpleResults(Filter):
    @attr
    def first_freq(self) -> float:
        return 12.34

    @attr
    def freq_at(self, mode: int = 1) -> float:
        return 12.34 + mode

    def not_an_attr(self) -> int:
        return 99


class TestFilterBase:
    def test_name_must_be_identifier(self):
        with pytest.raises(ValueError):
            _SimpleResults(name="has-dash")

    def test_list_attrs(self):
        f = _SimpleResults(name="r")
        assert sorted(f.list_attrs()) == ["first_freq", "freq_at"]

    def test_get_attr_callable(self):
        f = _SimpleResults(name="r")
        assert f.get_attr_callable("first_freq")() == 12.34

    def test_unknown_attr_raises(self):
        f = _SimpleResults(name="r")
        with pytest.raises(KeyError):
            f.get_attr_callable("missing")

    def test_method_without_decorator_not_attr(self):
        f = _SimpleResults(name="r")
        with pytest.raises(KeyError):
            f.get_attr_callable("not_an_attr")


class TestRegistry:
    def test_register_and_get(self):
        reg = FilterRegistry()
        f = _SimpleResults(name="r")
        reg.register(f)
        assert reg.get("r") is f

    def test_duplicate_name_raises(self):
        reg = FilterRegistry()
        reg.register(_SimpleResults(name="x"))
        with pytest.raises(ValueError):
            reg.register(_SimpleResults(name="x"))

    def test_call_attr_caches(self):
        reg = FilterRegistry()
        calls: list[int] = []

        class Counter(Filter):
            @attr
            def value(self) -> int:
                calls.append(1)
                return len(calls)

        reg.register(Counter(name="c"))
        first = reg.call_attr("c", "value", {})
        second = reg.call_attr("c", "value", {})
        assert first == second == 1
        assert len(calls) == 1

    def test_call_attr_different_args_recompute(self):
        reg = FilterRegistry()
        reg.register(_SimpleResults(name="r"))
        a = reg.call_attr("r", "freq_at", {"mode": 1})
        b = reg.call_attr("r", "freq_at", {"mode": 2})
        assert a == 13.34
        assert b == 14.34

    def test_unexpected_kwarg_rejected(self):
        reg = FilterRegistry()
        reg.register(_SimpleResults(name="r"))
        with pytest.raises(TypeError, match="unexpected keyword"):
            reg.call_attr("r", "first_freq", {"bogus": 1})

    def test_unknown_filter_name(self):
        reg = FilterRegistry()
        with pytest.raises(KeyError):
            reg.call_attr("missing", "x", {})


class TestCache:
    def test_args_hash_stable(self):
        a = _hash_args({"x": 1, "y": "a"})
        b = _hash_args({"y": "a", "x": 1})
        assert a == b

    def test_source_change_invalidates(self):
        class A(Filter):
            @attr
            def v(self) -> int:
                return 1

        cache = AttrCache()
        first = cache.get_or_compute(
            filter_name="x",
            attr_name="v",
            args={},
            filter_cls=A,
            compute=lambda: 42,
        )

        # New class with same name but different source
        class A:  # noqa: F811
            @attr
            def v(self) -> int:
                return 2  # changed source

        # New cache instance because the class object identity changed
        cache2 = AttrCache()
        second = cache2.get_or_compute(
            filter_name="x",
            attr_name="v",
            args={},
            filter_cls=A,
            compute=lambda: 100,
        )
        assert first == 42
        assert second == 100
