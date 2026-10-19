# -*- coding: utf-8 -*-
"""Moteur de formules Merka — évaluation sûre pour indicateurs."""
import ast
import math
import operator
import re

from odoo.exceptions import UserError


_CODE_RE = re.compile(r'\{([A-Za-z_][A-Za-z0-9_.-]*)\}')
_COMMENT_RE = re.compile(r'#.*?$', re.MULTILINE)

# Fonctions exposées aux formules
def _safe_div(a, b, default=0.0):
    try:
        a, b = float(a), float(b)
        if b == 0:
            return float(default)
        return a / b
    except (TypeError, ValueError):
        return float(default)


def _pct(part, total, default=0.0):
    """part / total * 100, sans division par zéro."""
    return _safe_div(part, total, default) * 100.0


def _growth(current, previous, default=0.0):
    """(current - previous) / |previous| * 100."""
    try:
        cur, prev = float(current), float(previous)
        if prev == 0:
            return 100.0 if cur else float(default)
        return ((cur - prev) / abs(prev)) * 100.0
    except (TypeError, ValueError):
        return float(default)


def _coalesce(*args):
    for a in args:
        if a is None:
            continue
        try:
            v = float(a)
            if v == v:  # not NaN
                return v
        except (TypeError, ValueError):
            continue
    return 0.0


def _iff(cond, a, b):
    return a if cond else b


def _clamp(value, low, high):
    return max(float(low), min(float(high), float(value)))


def _round(value, ndigits=0):
    return round(float(value), int(ndigits))


def _pow(base, exp):
    return float(base) ** float(exp)


FORMULA_FUNCS = {
    'abs': abs,
    'min': min,
    'max': max,
    'round': _round,
    'floor': lambda x: float(math.floor(float(x))),
    'ceil': lambda x: float(math.ceil(float(x))),
    'sqrt': lambda x: math.sqrt(float(x)),
    'pow': _pow,
    'safe_div': _safe_div,
    'div': _safe_div,
    'pct': _pct,
    'growth': _growth,
    'coalesce': _coalesce,
    'ifnull': _coalesce,
    'iff': _iff,
    'clamp': _clamp,
}

FORMULA_PRESETS = [
    ('none', '— Choisir un modèle —'),
    ('panier', 'Panier moyen → safe_div({ca}, {commandes})'),
    ('taux', 'Taux % → pct({ok}, {total})'),
    ('evolution', 'Évolution % → growth({actuel}, {precedent})'),
    ('marge', 'Marge % → pct({ca}-{cout}, {ca})'),
    ('conversion', 'Conversion % → pct({commandes}, {commandes}+{devis})'),
    ('ecart', 'Écart → {actuel} - {objectif}'),
    ('atteinte', 'Atteinte objectif % → pct({actuel}, {objectif})'),
]

PRESET_FORMULAS = {
    'panier': 'safe_div({ca}, {commandes})',
    'taux': 'pct({ok}, {total})',
    'evolution': 'growth({actuel}, {precedent})',
    'marge': 'pct({ca} - {cout}, {ca})',
    'conversion': 'pct({commandes}, {commandes} + {devis})',
    'ecart': '{actuel} - {objectif}',
    'atteinte': 'pct({actuel}, {objectif})',
}

# Guide utilisateur (HTML) — formulaires KPI / indicateurs
FORMULA_USER_GUIDE_HTML = """
<div class="o_merka_formula_guide">
  <h4 style="margin-top:0">Comment écrire une formule ?</h4>
  <ol>
    <li>
      Créez d’abord des indicateurs <b>simples</b> (source Odoo) avec un
      <b>code court</b> : par ex. <code>ca</code>, <code>commandes</code>, <code>devis</code>.
    </li>
    <li>
      Créez un indicateur (ou un KPI) en source / agrégation
      <b>Formule</b>.
    </li>
    <li>
      Référez-vous aux autres codes entre accolades :
      <code>{ca}</code>, <code>{commandes}</code>…
      Merka remplace chaque <code>{code}</code> par la valeur de la tuile
      correspondante <b>du même tableau</b>, puis calcule le résultat.
    </li>
  </ol>

  <h4>Exemple concret — panier moyen</h4>
  <table class="table table-sm table-bordered" style="max-width:520px">
    <thead><tr><th>Code</th><th>Indicateur</th><th>Valeur</th></tr></thead>
    <tbody>
      <tr><td><code>ca</code></td><td>Chiffre d’affaires</td><td>12&nbsp;000&nbsp;€</td></tr>
      <tr><td><code>commandes</code></td><td>Nb commandes</td><td>40</td></tr>
    </tbody>
  </table>
  <p>
    Formule :
    <code>safe_div({ca}, {commandes})</code>
    → <b>12&nbsp;000 ÷ 40 = 300&nbsp;€</b>
  </p>
  <p class="text-muted mb-2">
    <code>safe_div</code> évite l’erreur si le dénominateur vaut 0
    (résultat = 0 au lieu d’un crash).
  </p>

  <h4>Autres exemples prêts à coller</h4>
  <ul>
    <li>
      <b>Taux de conversion</b> :
      <code>pct({commandes}, {commandes} + {devis})</code>
      → pourcentage (ex. 40 / 100 = 40&nbsp;%)
    </li>
    <li>
      <b>Évolution CA</b> :
      <code>growth({ca}, {ca_n1})</code>
      → % de variation vs période précédente
    </li>
    <li>
      <b>Marge</b> :
      <code>pct({ca} - {cout}, {ca})</code>
    </li>
    <li>
      <b>Atteinte d’objectif</b> :
      <code>pct({actuel}, {objectif})</code>
    </li>
  </ul>

  <h4>Fonctions utiles</h4>
  <ul class="mb-0">
    <li><code>safe_div(a, b)</code> — division sûre</li>
    <li><code>pct(a, b)</code> — a ÷ b × 100</li>
    <li><code>growth(actuel, precedent)</code> — évolution %</li>
    <li><code>coalesce(a, b, …)</code> — première valeur non vide</li>
    <li><code>iff(cond, a, b)</code> — si / sinon</li>
    <li><code>round, abs, min, max, clamp</code> — arrondi et bornes</li>
    <li>Commentaire : tout après <code>#</code> est ignoré</li>
  </ul>
  <p class="mt-2 mb-0">
    <b>Astuce</b> : utilisez le menu <i>Modèle de formule</i> pour remplir
    automatiquement un modèle métier, puis adaptez les codes
    (<code>{ca}</code>, …) à ceux de votre tableau.
  </p>
</div>
"""


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}
_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


class FormulaError(UserError):
    pass


def extract_codes(expr):
    """Liste ordonnée unique des {codes} dans une formule."""
    if not expr:
        return []
    seen, out = set(), []
    for code in _CODE_RE.findall(expr):
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out


def strip_comments(expr):
    return _COMMENT_RE.sub('', expr or '').strip()


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):  # py3.8+
        if isinstance(node.value, (int, float, bool)):
            return float(node.value) if not isinstance(node.value, bool) else node.value
        raise FormulaError('Constante non autorisée dans la formule.')
    if isinstance(node, ast.Num):  # pragma: no cover - py<3.8
        return float(node.n)
    if isinstance(node, ast.Name):
        if node.id in FORMULA_FUNCS:
            return FORMULA_FUNCS[node.id]
        raise FormulaError('Identifiant inconnu : %s' % node.id)
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if not op:
            raise FormulaError('Opérateur non autorisé.')
        left, right = _eval_node(node.left), _eval_node(node.right)
        try:
            return op(left, right)
        except ZeroDivisionError:
            return 0.0
    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if not op:
            raise FormulaError('Opérateur unaire non autorisé.')
        return op(_eval_node(node.operand))
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left)
        for op_node, comparator in zip(node.ops, node.comparators):
            op = _CMP_OPS.get(type(op_node))
            if not op:
                raise FormulaError('Comparaison non autorisée.')
            right = _eval_node(comparator)
            if not op(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            val = True
            for v in node.values:
                val = _eval_node(v)
                if not val:
                    return False
            return val
        if isinstance(node.op, ast.Or):
            for v in node.values:
                val = _eval_node(v)
                if val:
                    return val
            return False
        raise FormulaError('Booléen non autorisé.')
    if isinstance(node, ast.IfExp):
        return _eval_node(node.body) if _eval_node(node.test) else _eval_node(node.orelse)
    if isinstance(node, ast.Call):
        func = _eval_node(node.func)
        if func not in FORMULA_FUNCS.values():
            raise FormulaError('Fonction non autorisée.')
        args = [_eval_node(a) for a in node.args]
        if node.keywords:
            raise FormulaError('Arguments nommés non autorisés.')
        try:
            return func(*args)
        except ZeroDivisionError:
            return 0.0
        except Exception as exc:
            raise FormulaError('Erreur fonction : %s' % exc) from exc
    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(e) for e in node.elts)
    raise FormulaError('Expression non autorisée (%s).' % type(node).__name__)


def evaluate_formula(expr, variables=None):
    """
    Évalue une formule Merka.
    :param expr: texte avec {codes} et/ou valeurs déjà substituées
    :param variables: dict code -> float (si {codes} encore présents)
    :return: float
    """
    expr = strip_comments(expr)
    if not expr:
        raise FormulaError('Formule vide.')

    variables = variables or {}
    # Remplace {code} par littéraux numériques
    def _repl(match):
        code = match.group(1)
        val = variables.get(code, 0.0)
        try:
            val = float(val)
        except (TypeError, ValueError):
            val = 0.0
        return ('(%s)' % val)

    substituted = _CODE_RE.sub(_repl, expr)
    # Interdit tout identifiant hors fonctions connues (après sub, plus de { })
    try:
        tree = ast.parse(substituted, mode='eval')
    except SyntaxError as exc:
        raise FormulaError('Syntaxe invalide : %s' % exc.msg) from exc

    result = _eval_node(tree)
    try:
        result = float(result)
    except (TypeError, ValueError):
        result = 1.0 if result else 0.0
    if result != result or result in (float('inf'), float('-inf')):
        return 0.0
    return result


def format_help_html():
    return (
        "<ul class='mb-0'>"
        "<li><b>Références</b> : <code>{ca}</code>, <code>{commandes}</code> (codes des indicateurs)</li>"
        "<li><b>Opérateurs</b> : + − * / % ** ( ) et comparaisons &lt; &gt; &lt;= &gt;= == !=</li>"
        "<li><b>safe_div(a,b)</b> / <b>div(a,b)</b> : division sans erreur si b=0</li>"
        "<li><b>pct(a,b)</b> : a/b×100</li>"
        "<li><b>growth(actuel, precedent)</b> : évolution en %</li>"
        "<li><b>coalesce(a,b,…)</b> : première valeur non nulle</li>"
        "<li><b>iff(cond, a, b)</b> ou <code>a if cond else b</code></li>"
        "<li><b>abs, min, max, round, floor, ceil, sqrt, pow, clamp</b></li>"
        "<li>Commentaires : <code># texte ignoré</code></li>"
        "</ul>"
    )
