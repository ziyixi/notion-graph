from app.notion.parser import deterministic_edge_id, infer_node_type, parse_block_edges


def test_deterministic_edge_id_stable() -> None:
    one = deterministic_edge_id("a", "b", "mention", None, "x")
    two = deterministic_edge_id("a", "b", "mention", None, "x")
    assert one == two


def test_parse_structured_relation_block() -> None:
    block = {
        "id": "block1",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {"type": "text", "plain_text": "works_with -> "},
                {
                    "type": "mention",
                    "plain_text": "@Bob",
                    "mention": {"type": "page", "page": {"id": "bob"}},
                },
            ]
        },
    }

    parsed = parse_block_edges("alice", block)
    assert len(parsed.edges) == 1
    edge = parsed.edges[0]
    assert edge.relationType == "structured_relation"
    assert edge.label == "works_with"


def test_parse_link_to_page_block() -> None:
    block = {
        "id": "block2",
        "type": "link_to_page",
        "link_to_page": {"type": "page_id", "page_id": "paper"},
    }

    parsed = parse_block_edges("alice", block)
    assert len(parsed.edges) == 1
    assert parsed.edges[0].relationType == "link_to_page"
    assert parsed.edges[0].targetId == "paper"


def test_parse_plain_mention_block() -> None:
    block = {
        "id": "block3",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {"type": "text", "plain_text": "Ping "},
                {
                    "type": "mention",
                    "plain_text": "@Bob",
                    "mention": {"type": "page", "page": {"id": "bob"}},
                },
            ]
        },
    }

    parsed = parse_block_edges("alice", block)
    assert len(parsed.edges) == 1
    assert parsed.edges[0].relationType == "mention"
    assert parsed.edges[0].targetId == "bob"


def test_type_inference_priority() -> None:
    inferred = infer_node_type(
        title="Alice",
        ancestor_titles=["People"],
        extracted_lines=["Type: Project", "Template: Person"],
    )
    assert inferred == "project"

    inferred_from_ancestor = infer_node_type(
        title="Bob",
        ancestor_titles=["People"],
        extracted_lines=[],
    )
    assert inferred_from_ancestor == "person"


def test_type_inference_artifact_fallback() -> None:
    inferred = infer_node_type(
        title="Meeting Note 3/8",
        ancestor_titles=["Misc"],
        extracted_lines=[],
    )
    assert inferred == "artifact"
