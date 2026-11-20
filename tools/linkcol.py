"""Link columns for VIEW-page grids: the cell links a record (a Workday object or one of the app's own records), and the
link's related-actions menu lists that record's tasks. Text when there is no WID. Used by every builder with a VIEW grid
(CLAUDE.md "Related actions in a VIEW grid")."""


def link_col(cid, label, id_expr, desc_expr, excel=False):
    base = cid[:-6] if cid.endswith("Column") else cid
    c = {"type": "column", "columnId": cid, "label": label, "cellTemplate": {"type": "fieldSet", "id": base + "LinkFieldSet", "children": [
        {"type": "instanceList", "id": base + "LinkInstanceList", "visible": "<% !empty(" + id_expr + ") %>",
         "values": "<% empty(" + id_expr + ") ? [] : [{'id': " + id_expr + ", 'descriptor': " + desc_expr + "}] %>",
         "widKey": "id", "view": True, "relatedTask": True},
        {"type": "text", "id": base + "LinkText", "enabled": False, "visible": "<% empty(" + id_expr + ") %>", "value": "<% " + desc_expr + " %>"}]}}
    if excel:
        c["excel"] = {"value": "<% " + desc_expr + " %>"}
    return c
