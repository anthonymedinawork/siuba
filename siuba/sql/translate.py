from sqlalchemy import sql
from sqlalchemy.sql import sqltypes as types
from functools import singledispatch
from .verbs import case_when, if_else

# TODO: must make these take both tbl, col as args, since hard to find window funcs
def sa_is_window(clause):
    return isinstance(clause, sql.elements.Over) \
            or isinstance(clause, sql.elements.WithinGroup)


def sa_modify_window(clause, group_by = None, order_by = None):
    if group_by:
        group_cols = [columns[name] for name in group_by]
        partition_by = sql.elements.ClauseList(*group_cols)
        clone = clause._clone()
        clone.partition_by = partition_by

        return clone

    return clause

from sqlalchemy.sql.elements import Over
# windowed agg (group by)
# agg
# windowed scalar
# ordered set agg

class CustomOverClause: pass

class AggOver(Over, CustomOverClause):
    def set_over(self, group_by, order_by = None):
        self.partition_by = group_by
        return self


class RankOver(Over, CustomOverClause): 
    def set_over(self, group_by, order_by = None):
        self.partition_by = group_by
        return self


class CumlOver(Over, CustomOverClause):
    def set_over(self, group_by, order_by):
        self.partition_by = group_by
        self.order_by = order_by
        return self


def win_absent(name):
    def not_implemented(*args, **kwargs):
        raise NotImplementedError("SQL dialect does not support {}.".format(name))
    
    return not_implemented

def win_over(name):
    sa_func = getattr(sql.func, name)
    return lambda col: RankOver(sa_func(), order_by = col)

def win_cumul(name):
    sa_func = getattr(sql.func, name)
    return lambda col: CumlOver(sa_func(col), rows = (None,0))

def win_agg(name):
    sa_func = getattr(sql.func, name)
    return lambda col: AggOver(sa_func(col))

def sql_agg(name):
    sa_func = getattr(sql.func, name)
    return lambda col: sa_func(col)

def sql_scalar(name):
    sa_func = getattr(sql.func, name)
    return lambda col: sa_func(col)

def sql_colmeth(meth):
    def f(col, *args):
        return getattr(col, meth)(*args)
    return f

def sql_astype(col, _type):
    mappings = {
            str: types.Text,
            int: types.Integer,
            float: types.Numeric,
            bool: types.Boolean
            }
    sa_type = mappings[_type]
    return sql.cast(col, sa_type)

base_scalar = dict(
        # TODO: these methods are sqlalchemy ColumnElement methods, simplify?
        cast = sql_colmeth("cast"),
        startswith = sql_colmeth("startswith"),
        endswith = sql_colmeth("endswith"),
        between = sql_colmeth("between"),
        isin = sql_colmeth("in_"),
        # these are methods on sql.funcs ---- 
        abs = sql_scalar("abs"),
        acos = sql_scalar("acos"),
        asin = sql_scalar("asin"),
        atan = sql_scalar("atan"),
        atan2 = sql_scalar("atan2"),
        cos = sql_scalar("cos"),
        cot = sql_scalar("cot"),
        astype = sql_astype,
        # I was lazy here and wrote lambdas directly ---
        # TODO: I think these are postgres specific?
        hour = lambda col: sql.func.date_trunc('hour', col),
        week = lambda col: sql.func.date_trunc('week', col),
        isna = lambda col: col.is_(None),
        isnull = lambda col: col.is_(None),
        # dply.vector funcs ----
        desc = lambda col: col.desc(),
        
        # TODO: string methods
        #str.len,
        #str.upper,
        #str.lower,
        #str.replace_all or something similar,
        #str_detect or similar,
        #str_trim func to cut text off sides
        # TODO: move to postgres specific
        n = lambda col: sql.func.count(),
        sum = sql_scalar("sum"),
        # TODO: this is to support a DictCall (e.g. used in case_when)
        dict = dict,
        # TODO: don't use singledispatch to add sql support to case_when
        case_when = case_when,
        if_else = if_else
        )

base_agg = dict(
        mean = sql_agg("avg"),
        # TODO: generalize case where doesn't use col
        # need better handeling of vector funcs
        len = lambda col: sql.func.count()
        )

base_win = dict(
        row_number = win_over("row_number"),
        min_rank = win_over("rank"),
        rank = win_over("rank"),
        dense_rank = win_over("dense_rank"),
        percent_rank = win_over("percent_rank"),
        cume_dist = win_over("cume_dist"),
        #first = win_over2("first"),
        #last = win_over2("last"),
        #nth = win_over3
        #lead = win_over4
        #lag

        # aggregate functions ---
        mean = win_agg("avg"),
        var = win_agg("variance"),
        sum = win_agg("sum"),
        min = win_agg("min"),
        max = win_agg("max"),

        # ordered set funcs ---
        #quantile
        #median

        # counts ----
        len = lambda col: sql.func.count().over(),
        #n
        #n_distinct

        # cumulative funcs ---
        #avg("id") OVER (PARTITION BY "email" ORDER BY "id" ROWS UNBOUNDED PRECEDING)
        #cummean = win_agg("
        cumsum = win_cumul("sum")
        #cummin
        #cummax

        )

# based on https://github.com/tidyverse/dbplyr/blob/master/R/backend-.R
base_nowin = dict(
        row_number   = win_absent("ROW_NUMBER"),
        min_rank     = win_absent("RANK"),
        rank         = win_absent("RANK"),
        dense_rank   = win_absent("DENSE_RANK"),
        percent_rank = win_absent("PERCENT_RANK"),
        cume_dist    = win_absent("CUME_DIST"),
        ntile        = win_absent("NTILE"),
        mean         = win_absent("AVG"),
        sd           = win_absent("SD"),
        var          = win_absent("VAR"),
        cov          = win_absent("COV"),
        cor          = win_absent("COR"),
        sum          = win_absent("SUM"),
        min          = win_absent("MIN"),
        max          = win_absent("MAX"),
        median       = win_absent("PERCENTILE_CONT"),
        quantile    = win_absent("PERCENTILE_CONT"),
        n            = win_absent("N"),
        n_distinct   = win_absent("N_DISTINCT"),
        cummean      = win_absent("MEAN"),
        cumsum       = win_absent("SUM"),
        cummin       = win_absent("MIN"),
        cummax       = win_absent("MAX"),
        nth          = win_absent("NTH_VALUE"),
        first        = win_absent("FIRST_VALUE"),
        last         = win_absent("LAST_VALUE"),
        lead         = win_absent("LEAD"),
        lag          = win_absent("LAG"),
        order_by     = win_absent("ORDER_BY"),
        str_flatten  = win_absent("STR_FLATTEN"),
        count        = win_absent("COUNT")
        )

funcs = dict(scalar = base_scalar, aggregate = base_agg, window = base_win)

# MISC ===========================================================================
# scalar, aggregate, window #no_win, agg_no_win

# local to table
# alias to LazyTbl.no_win.dense_rank...
#          LazyTbl.agg.dense_rank...

from collections.abc import Mapping
import itertools

class SqlTranslator(Mapping):
    def __init__(self, d, **kwargs):
        self.d = d
        self.kwargs = kwargs

    def __len__(self):
        return len(set(self.d) + set(self.kwargs))

    def __iter__(self):
        old_keys = iter(self.d)
        new_keys = (k for k in self.kwargs if k not in self.d)
        return itertools.chain(old_keys, new_keys)

    def __getitem__(self, x):
        try:
            return self.kwargs[x]
        except KeyError:
            return self.d[x]
