"""
data_structures.py
Custom data structures for StructDB.
  - HashTable : O(1) average point lookups via separate chaining
  - BTree     : O(log n) ordered index with range-query support
"""


# ══════════════════════════════════════════════════════════════════════════════
#  Hash Table — separate chaining
# ══════════════════════════════════════════════════════════════════════════════

class Node:
    """Linked-list node used for collision chaining in HashTable."""
    def __init__(self, key, value):
        self.key   = key
        self.value = value
        self.next  = None


class HashTable:
    """Hash Table with separate chaining — O(1) average insert / search / delete."""

    def __init__(self, size=100):
        self.size  = size
        self.table = [None] * size
        self.count = 0

    def _hash(self, key):
        return hash(str(key)) % self.size

    def insert(self, key, value):
        idx = self._hash(key)
        if self.table[idx] is None:
            self.table[idx] = Node(key, value)
            self.count += 1
        else:
            cur = self.table[idx]
            while cur:
                if cur.key == key:
                    cur.value = value   # update existing
                    return
                if cur.next is None:
                    break
                cur = cur.next
            cur.next = Node(key, value)
            self.count += 1

    def get(self, key):
        cur = self.table[self._hash(key)]
        while cur:
            if cur.key == key:
                return cur.value
            cur = cur.next
        return None

    def delete(self, key):
        idx  = self._hash(key)
        cur  = self.table[idx]
        prev = None
        while cur:
            if cur.key == key:
                if prev:
                    prev.next = cur.next
                else:
                    self.table[idx] = cur.next
                self.count -= 1
                return True
            prev, cur = cur, cur.next
        return False

    def all_values(self):
        result = []
        for node in self.table:
            cur = node
            while cur:
                result.append(cur.value)
                cur = cur.next
        return result


# ══════════════════════════════════════════════════════════════════════════════
#  B-Tree — ordered index, supports range queries
# ══════════════════════════════════════════════════════════════════════════════

class BTreeNode:
    """A single node in a B-Tree."""
    def __init__(self, leaf=False):
        self.keys     = []   # sorted key list
        self.values   = []   # values parallel to keys
        self.children = []   # child BTreeNodes (empty when leaf)
        self.leaf     = leaf


class BTree:
    """
    B-Tree of minimum degree *t* (default 3).

    Properties
    ----------
    * Each internal node holds between t-1 and 2t-1 keys.
    * Supports insert, point-search O(log n), and range-search O(log n + k).
    * In-order traversal yields all records in sorted key order.

    Why B-Trees in real databases
    ------------------------------
    Unlike a hash table, a B-Tree keeps keys sorted, making range predicates
    (WHERE age > 20 AND age < 30) efficient. MySQL InnoDB and PostgreSQL both
    use B+-Tree variants for their primary indexes.
    """

    def __init__(self, t=3):
        self.root = BTreeNode(leaf=True)
        self.t    = t   # minimum degree

    # ── point search ─────────────────────────────────────────────────────────
    def search(self, key, node=None):
        """Return stored value for *key*, or None if absent."""
        key = str(key)
        if node is None:
            node = self.root
        i = 0
        while i < len(node.keys) and key > node.keys[i]:
            i += 1
        if i < len(node.keys) and key == node.keys[i]:
            return node.values[i]
        if node.leaf:
            return None
        return self.search(key, node.children[i])

    # ── insert ───────────────────────────────────────────────────────────────
    def insert(self, key, value):
        """Insert or update *key* → *value*."""
        key = str(key)
        if len(self.root.keys) == 2 * self.t - 1:
            new_root = BTreeNode(leaf=False)
            new_root.children.append(self.root)
            self._split_child(new_root, 0)
            self.root = new_root
        self._insert_nonfull(self.root, key, value)

    def _insert_nonfull(self, node, key, value):
        i = len(node.keys) - 1
        if node.leaf:
            node.keys.append(None)
            node.values.append(None)
            while i >= 0 and key < node.keys[i]:
                node.keys[i + 1]   = node.keys[i]
                node.values[i + 1] = node.values[i]
                i -= 1
            if i >= 0 and node.keys[i] == key:   # overwrite
                node.values[i] = value
                node.keys.pop(); node.values.pop()
            else:
                node.keys[i + 1]   = key
                node.values[i + 1] = value
        else:
            while i >= 0 and key < node.keys[i]:
                i -= 1
            i += 1
            if len(node.children[i].keys) == 2 * self.t - 1:
                self._split_child(node, i)
                if key > node.keys[i]:
                    i += 1
            self._insert_nonfull(node.children[i], key, value)

    def _split_child(self, parent, i):
        t     = self.t
        child = parent.children[i]
        mid   = t - 1
        new   = BTreeNode(leaf=child.leaf)

        parent.keys.insert(i, child.keys[mid])
        parent.values.insert(i, child.values[mid])
        parent.children.insert(i + 1, new)

        new.keys   = child.keys[mid + 1:]
        new.values = child.values[mid + 1:]
        if not child.leaf:
            new.children   = child.children[mid + 1:]
            child.children = child.children[:mid + 1]
        child.keys   = child.keys[:mid]
        child.values = child.values[:mid]

    # ── range search ─────────────────────────────────────────────────────────
    def range_search(self, low=None, high=None):
        """Return [(key, value), ...] for all keys in [low, high] (inclusive)."""
        lo = str(low)  if low  is not None else None
        hi = str(high) if high is not None else None
        results = []
        self._range_helper(self.root, lo, hi, results)
        return results

    def _range_helper(self, node, lo, hi, results):
        for i, k in enumerate(node.keys):
            if not node.leaf:
                self._range_helper(node.children[i], lo, hi, results)
            in_range = (lo is None or k >= lo) and (hi is None or k <= hi)
            if in_range:
                results.append((k, node.values[i]))
        if not node.leaf and node.children:
            self._range_helper(node.children[-1], lo, hi, results)

    # ── in-order traversal ───────────────────────────────────────────────────
    def to_sorted_list(self):
        """Return all (key, value) pairs in ascending key order."""
        result = []
        self._inorder(self.root, result)
        return result

    def _inorder(self, node, result):
        if node.leaf:
            for k, v in zip(node.keys, node.values):
                result.append((k, v))
        else:
            for i, (k, v) in enumerate(zip(node.keys, node.values)):
                self._inorder(node.children[i], result)
                result.append((k, v))
            if node.children:
                self._inorder(node.children[-1], result)