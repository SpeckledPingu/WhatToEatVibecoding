"""
join_keys.py — Create standardized join keys for matching across data sources.

WHAT IS A JOIN KEY?
In databases, a "join" is the operation that connects rows from different tables.
For example, connecting a receipt item to a recipe ingredient. But to join, you
need a shared identifier — something BOTH tables have in common. That shared
identifier is the join key.

THE PROBLEM
Our data sources have NO shared identifier:
  - Receipt: item_name = "Publix Unsltd Btr Ft", id = 42
  - Pantry:  item_name = "butter", id = 7
  - Recipe:  ingredient name = "butter"

None of these IDs or names match each other directly.

THE SOLUTION
We CREATE a join key by normalizing each item to a standard form:
  - Receipt "Publix Unsltd Btr Ft" → normalized "butter" → key "dairy:butter"
  - Pantry "butter" → normalized "butter" → key "dairy:butter"
  - Recipe "butter" → normalized "butter" → key "dairy:butter"

Now all three produce "dairy:butter", so the database can match them.

WHY INCLUDE CATEGORY IN THE KEY?
Without category, "turkey" the meat and a hypothetical "turkey" in another context
would have the same key. Including the category as a prefix ("protein:turkey")
prevents these false matches. It also makes the key human-readable — you can tell
at a glance that "dairy:butter" is a dairy product.

HOW JOIN KEYS RELATE TO DATABASE FOREIGN KEYS
A foreign key in a database is a column that references another table's primary key.
Join keys serve a similar purpose but are DERIVED rather than stored as references.
Foreign keys enforce relationships at the schema level; join keys enable matching
at the data level when no formal relationship exists between tables.

RUN IT:
    uv run python -m src.normalization.join_keys
"""


def create_join_key(normalized_name: str, category: str) -> str:
    """
    Create a standardized join key from a normalized food name and category.

    The key format is: "{category}:{normalized_name}"

    This key uniquely identifies a food item across all data sources. When the
    same food appears in receipts, pantry, and recipes, they all produce the
    same join key — enabling database joins even though the original data had
    no shared identifiers.

    Parameters:
        normalized_name: The cleaned, standardized food name (e.g., "butter").
                         Should already be lowercased and alias-resolved.
        category: The standardized food category (e.g., "dairy").

    Returns:
        A join key string like "dairy:butter".

    Examples:
        >>> create_join_key("butter", "dairy")
        'dairy:butter'
        >>> create_join_key("chicken breast", "protein")
        'protein:chicken breast'
        >>> create_join_key("olive oil", "condiment")
        'condiment:olive oil'
    """
    # Both parts should already be lowercase from normalization, but we
    # enforce it here as a safety net — inconsistent casing would break joins
    clean_name = normalized_name.strip().lower()
    clean_category = category.strip().lower()

    return f"{clean_category}:{clean_name}"


# ---------------------------------------------------------------------------
# Demo / test section — shows how the join key works with real data
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("JOIN KEY DEMONSTRATION")
    print("=" * 70)
    print()
    print("Join keys combine category + normalized name into a single identifier")
    print("that works across all data sources (receipts, pantry, recipes).")
    print()

    # Examples from actual data showing how different source names
    # produce the SAME join key after normalization
    examples = [
        # (source, original_name, normalized_name, category)
        ("receipt", "Publix Unsltd Btr Ft", "butter", "dairy"),
        ("pantry", "butter", "butter", "dairy"),
        ("recipe", "butter", "butter", "dairy"),
        ("---", "", "", ""),
        ("receipt", "Gld Mdl AP Flour 5lb Ft", "flour", "grain"),
        ("pantry", "all purpose flour", "flour", "grain"),
        ("recipe", "flour", "flour", "grain"),
        ("---", "", "", ""),
        ("receipt", "Ground Round (15% Fat) Ft", "ground beef", "protein"),
        ("recipe", "ground beef", "ground beef", "protein"),
        ("---", "", "", ""),
        ("receipt", "Barilla Spaghetti Ft", "pasta", "grain"),
        ("pantry", "spaghetti", "spaghetti", "grain"),
        ("recipe", "spaghetti", "spaghetti", "grain"),
    ]

    print(f"{'Source':<10} {'Original Name':<30} {'Normalized':<18} {'Join Key'}")
    print("-" * 85)

    for source, original, normalized, category in examples:
        if source == "---":
            print()
            continue
        key = create_join_key(normalized, category)
        print(f"{source:<10} {original:<30} {normalized:<18} {key}")

    print()
    print("Notice how different original names from different sources produce")
    print("the SAME join key — that's what enables matching across tables.")
