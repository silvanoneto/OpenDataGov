"""Tests for metadata schema, adapters (DataHub, OpenLineage), and protocol."""

from __future__ import annotations

import uuid
from typing import Any

from odg_core.enums import DataClassification, MedallionLayer
from odg_core.metadata import MetadataCatalog
from odg_core.metadata.datahub_adapter import datahub_to_odg, odg_to_datahub_mce
from odg_core.metadata.odg_schema import DatasetField, ODGDatasetMetadata
from odg_core.metadata.openlineage_adapter import odg_to_openlineage_dataset

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_field(
    *,
    name: str = "col_a",
    data_type: str = "string",
    description: str = "A column",
    is_pii: bool = False,
    is_nullable: bool = True,
) -> DatasetField:
    return DatasetField(
        name=name,
        data_type=data_type,
        description=description,
        is_pii=is_pii,
        is_nullable=is_nullable,
    )


_SENTINEL: list[DatasetField] = []


def _sample_metadata(
    *,
    dataset_id: str = "finance/revenue",
    name: str = "revenue",
    domain_id: str = "finance",
    owner_id: str = "team-data",
    fields: list[DatasetField] | None = _SENTINEL,
    quality_score: float | None = 0.95,
) -> ODGDatasetMetadata:
    resolved_fields = [_sample_field()] if fields is _SENTINEL else (fields or [])
    return ODGDatasetMetadata(
        dataset_id=dataset_id,
        name=name,
        domain_id=domain_id,
        owner_id=owner_id,
        schema_fields=resolved_fields,
        quality_score=quality_score,
    )


# ---------------------------------------------------------------------------
# DatasetField
# ---------------------------------------------------------------------------


class TestDatasetField:
    def test_minimal_creation(self) -> None:
        f = DatasetField(name="id", data_type="integer")
        assert f.name == "id"
        assert f.data_type == "integer"
        assert f.description == ""
        assert f.is_pii is False
        assert f.is_nullable is True

    def test_full_creation(self) -> None:
        f = DatasetField(
            name="email",
            data_type="string",
            description="User email",
            is_pii=True,
            is_nullable=False,
        )
        assert f.name == "email"
        assert f.is_pii is True
        assert f.is_nullable is False
        assert f.description == "User email"

    def test_serialization_roundtrip(self) -> None:
        f = _sample_field(name="x", data_type="float", is_pii=True, is_nullable=False)
        data = f.model_dump()
        restored = DatasetField(**data)
        assert restored == f


# ---------------------------------------------------------------------------
# ODGDatasetMetadata
# ---------------------------------------------------------------------------


class TestODGDatasetMetadata:
    def test_defaults(self) -> None:
        m = ODGDatasetMetadata(
            dataset_id="ds/1",
            name="ds_one",
            domain_id="analytics",
            owner_id="alice",
        )
        assert m.layer == MedallionLayer.BRONZE
        assert m.classification == DataClassification.INTERNAL
        assert m.tags == []
        assert m.schema_fields == []
        assert m.quality_score is None
        assert m.contract_id is None
        assert m.jurisdiction is None
        assert m.pii_columns == []
        assert m.created_at is None
        assert m.updated_at is None
        assert isinstance(m.id, uuid.UUID)
        assert m.description == ""

    def test_full_construction(self) -> None:
        contract_id = uuid.uuid4()
        f = _sample_field(name="ssn", is_pii=True)
        m = ODGDatasetMetadata(
            dataset_id="hr/employees",
            name="employees",
            description="Employee master",
            domain_id="hr",
            owner_id="hr-team",
            layer=MedallionLayer.GOLD,
            classification=DataClassification.CONFIDENTIAL,
            tags=["sensitive", "hr"],
            schema_fields=[f],
            quality_score=0.98,
            contract_id=contract_id,
            jurisdiction="br",
            pii_columns=["ssn"],
        )
        assert m.layer == MedallionLayer.GOLD
        assert m.classification == DataClassification.CONFIDENTIAL
        assert m.tags == ["sensitive", "hr"]
        assert len(m.schema_fields) == 1
        assert m.schema_fields[0].is_pii is True
        assert m.quality_score == 0.98
        assert m.contract_id == contract_id
        assert m.jurisdiction == "br"
        assert m.pii_columns == ["ssn"]

    def test_serialization_roundtrip(self) -> None:
        m = _sample_metadata()
        data = m.model_dump()
        restored = ODGDatasetMetadata(**data)
        assert restored.dataset_id == m.dataset_id
        assert restored.name == m.name
        assert len(restored.schema_fields) == len(m.schema_fields)


# ---------------------------------------------------------------------------
# DataHub adapter — odg_to_datahub_mce
# ---------------------------------------------------------------------------


class TestOdgToDatahubMce:
    def test_basic_structure(self) -> None:
        m = _sample_metadata()
        mce = odg_to_datahub_mce(m)

        assert mce["entityType"] == "dataset"
        assert mce["aspectName"] == "schemaMetadata"
        assert mce["changeType"] == "UPSERT"
        assert "finance/revenue" in mce["entityUrn"]
        assert "opendatagov" in mce["entityUrn"]
        assert "PROD" in mce["entityUrn"]

    def test_entity_urn_format(self) -> None:
        m = _sample_metadata(dataset_id="my/dataset")
        mce = odg_to_datahub_mce(m)
        expected = "urn:li:dataset:(urn:li:dataPlatform:opendatagov,my/dataset,PROD)"
        assert mce["entityUrn"] == expected

    def test_schema_name_from_metadata(self) -> None:
        m = _sample_metadata(name="my_schema_name")
        mce = odg_to_datahub_mce(m)
        assert mce["aspect"]["schemaName"] == "my_schema_name"

    def test_platform(self) -> None:
        m = _sample_metadata()
        mce = odg_to_datahub_mce(m)
        assert mce["aspect"]["platform"] == "urn:li:dataPlatform:opendatagov"

    def test_primary_keys_empty(self) -> None:
        m = _sample_metadata()
        mce = odg_to_datahub_mce(m)
        assert mce["aspect"]["primaryKeys"] == []

    def test_fields_mapping(self) -> None:
        fields = [
            _sample_field(name="user_id", data_type="integer", description="PK"),
            _sample_field(name="email", data_type="string", description="Email", is_pii=True, is_nullable=False),
        ]
        m = _sample_metadata(fields=fields)
        mce = odg_to_datahub_mce(m)

        mce_fields = mce["aspect"]["fields"]
        assert len(mce_fields) == 2

        # First field
        f0 = mce_fields[0]
        assert f0["fieldPath"] == "user_id"
        assert f0["nativeDataType"] == "integer"
        assert f0["description"] == "PK"
        assert f0["nullable"] is True
        assert f0["globalTags"]["tags"] == []  # not PII

        # Second field (PII)
        f1 = mce_fields[1]
        assert f1["fieldPath"] == "email"
        assert f1["nullable"] is False
        tags = f1["globalTags"]["tags"]
        assert len(tags) == 1
        assert tags[0]["tag"] == "urn:li:tag:PII"

    def test_no_fields(self) -> None:
        m = _sample_metadata(fields=[])
        mce = odg_to_datahub_mce(m)
        assert mce["aspect"]["fields"] == []


# ---------------------------------------------------------------------------
# DataHub adapter — datahub_to_odg
# ---------------------------------------------------------------------------


class TestDatahubToOdg:
    def test_basic_roundtrip(self) -> None:
        """Converting ODG -> DataHub -> ODG should preserve key fields."""
        original = _sample_metadata(
            dataset_id="test/ds",
            name="test_name",
            fields=[_sample_field(name="col1", data_type="string", description="d")],
        )
        mce = odg_to_datahub_mce(original)
        restored = datahub_to_odg(mce)

        assert restored.dataset_id == "test/ds"
        assert restored.name == "test_name"
        assert len(restored.schema_fields) == 1
        assert restored.schema_fields[0].name == "col1"
        assert restored.schema_fields[0].data_type == "string"
        assert restored.schema_fields[0].description == "d"

    def test_parses_dataset_id_from_urn(self) -> None:
        mce: dict[str, Any] = {
            "entityUrn": "urn:li:dataset:(urn:li:dataPlatform:opendatagov,my_dataset,PROD)",
            "aspect": {"schemaName": "my_schema", "fields": []},
        }
        result = datahub_to_odg(mce)
        assert result.dataset_id == "my_dataset"
        assert result.name == "my_schema"

    def test_fallback_when_no_comma_in_urn(self) -> None:
        mce: dict[str, Any] = {
            "entityUrn": "some-urn-without-commas",
            "aspect": {"fields": []},
        }
        result = datahub_to_odg(mce)
        assert result.dataset_id == "some-urn-without-commas"

    def test_defaults_for_unknown_fields(self) -> None:
        mce: dict[str, Any] = {
            "entityUrn": "urn:li:dataset:(p,ds_id,ENV)",
            "aspect": {"fields": []},
        }
        result = datahub_to_odg(mce)
        assert result.domain_id == "unknown"
        assert result.owner_id == "unknown"

    def test_field_nullable_default(self) -> None:
        mce: dict[str, Any] = {
            "entityUrn": "urn:li:dataset:(p,d,E)",
            "aspect": {
                "schemaName": "s",
                "fields": [{"fieldPath": "x", "nativeDataType": "int"}],
            },
        }
        result = datahub_to_odg(mce)
        f = result.schema_fields[0]
        assert f.name == "x"
        assert f.data_type == "int"
        assert f.is_nullable is True
        assert f.description == ""
        assert f.is_pii is False

    def test_pii_detection_from_tags(self) -> None:
        mce: dict[str, Any] = {
            "entityUrn": "urn:li:dataset:(p,d,E)",
            "aspect": {
                "schemaName": "s",
                "fields": [
                    {
                        "fieldPath": "email",
                        "nativeDataType": "string",
                        "description": "Email",
                        "nullable": False,
                        "globalTags": {"tags": [{"tag": "urn:li:tag:PII"}]},
                    },
                ],
            },
        }
        result = datahub_to_odg(mce)
        assert result.schema_fields[0].is_pii is True

    def test_non_pii_when_tags_empty(self) -> None:
        mce: dict[str, Any] = {
            "entityUrn": "urn:li:dataset:(p,d,E)",
            "aspect": {
                "schemaName": "s",
                "fields": [
                    {
                        "fieldPath": "id",
                        "nativeDataType": "int",
                        "globalTags": {"tags": []},
                    },
                ],
            },
        }
        result = datahub_to_odg(mce)
        assert result.schema_fields[0].is_pii is False

    def test_empty_aspect(self) -> None:
        mce: dict[str, Any] = {
            "entityUrn": "urn:li:dataset:(p,d,E)",
        }
        result = datahub_to_odg(mce)
        assert result.schema_fields == []
        assert result.dataset_id == "d"
        assert result.name == "d"  # schemaName defaults to dataset_id

    def test_schema_name_defaults_to_dataset_id(self) -> None:
        mce: dict[str, Any] = {
            "entityUrn": "urn:li:dataset:(p,myid,E)",
            "aspect": {"fields": []},
        }
        result = datahub_to_odg(mce)
        assert result.name == "myid"

    def test_multiple_fields(self) -> None:
        mce: dict[str, Any] = {
            "entityUrn": "urn:li:dataset:(p,d,E)",
            "aspect": {
                "schemaName": "s",
                "fields": [
                    {"fieldPath": "a", "nativeDataType": "string"},
                    {"fieldPath": "b", "nativeDataType": "int"},
                    {"fieldPath": "c", "nativeDataType": "float"},
                ],
            },
        }
        result = datahub_to_odg(mce)
        assert len(result.schema_fields) == 3
        assert [f.name for f in result.schema_fields] == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# OpenLineage adapter — odg_to_openlineage_dataset
# ---------------------------------------------------------------------------


class TestOdgToOpenlineageDataset:
    def test_basic_structure(self) -> None:
        m = _sample_metadata(
            dataset_id="fin/rev",
            domain_id="finance",
            owner_id="team-fin",
            quality_score=0.88,
        )

        result = odg_to_openlineage_dataset(m)

        assert result["namespace"] == "opendatagov://finance"
        assert result["name"] == "fin/rev"
        assert "facets" in result

    def test_schema_facet(self) -> None:
        fields = [
            _sample_field(name="id", data_type="integer", description="Primary key"),
            _sample_field(name="name", data_type="string", description="Name"),
        ]
        m = _sample_metadata(fields=fields)

        result = odg_to_openlineage_dataset(m)
        schema_facet = result["facets"]["schema"]

        assert schema_facet["_producer"] == "opendatagov"
        assert "SchemaDatasetFacet" in schema_facet["_schemaURL"]
        assert len(schema_facet["fields"]) == 2

        f0 = schema_facet["fields"][0]
        assert f0["name"] == "id"
        assert f0["type"] == "integer"
        assert f0["description"] == "Primary key"

    def test_data_quality_facet(self) -> None:
        m = _sample_metadata(quality_score=0.72)
        result = odg_to_openlineage_dataset(m)

        dq_facet = result["facets"]["dataQualityMetrics"]
        assert dq_facet["_producer"] == "opendatagov"
        assert dq_facet["qualityScore"] == 0.72
        assert "DataQualityMetrics" in dq_facet["_schemaURL"]

    def test_quality_score_none(self) -> None:
        m = _sample_metadata(quality_score=None)
        result = odg_to_openlineage_dataset(m)
        assert result["facets"]["dataQualityMetrics"]["qualityScore"] is None

    def test_ownership_facet(self) -> None:
        m = _sample_metadata(owner_id="data-eng")
        result = odg_to_openlineage_dataset(m)

        ownership = result["facets"]["ownership"]
        assert ownership["_producer"] == "opendatagov"
        assert len(ownership["owners"]) == 1
        assert ownership["owners"][0]["name"] == "data-eng"
        assert ownership["owners"][0]["type"] == "DATAOWNER"

    def test_empty_schema_fields(self) -> None:
        m = _sample_metadata(fields=[])
        result = odg_to_openlineage_dataset(m)
        assert result["facets"]["schema"]["fields"] == []

    def test_namespace_derived_from_domain(self) -> None:
        m = _sample_metadata(domain_id="marketing")
        result = odg_to_openlineage_dataset(m)
        assert result["namespace"] == "opendatagov://marketing"


# ---------------------------------------------------------------------------
# Protocol — MetadataCatalog
# ---------------------------------------------------------------------------


class TestMetadataCatalogProtocol:
    def test_protocol_has_register_method(self) -> None:
        assert hasattr(MetadataCatalog, "register")

    def test_protocol_has_get_method(self) -> None:
        assert hasattr(MetadataCatalog, "get")

    def test_protocol_has_search_method(self) -> None:
        assert hasattr(MetadataCatalog, "search")

    def test_structural_subtyping(self) -> None:
        """A class implementing the three async methods satisfies the protocol at type-check time.

        Since MetadataCatalog is not @runtime_checkable, we verify that a
        conforming class can be assigned to the protocol type and that the
        expected methods exist and are callable.
        """

        class FakeCatalog:
            async def register(self, metadata: ODGDatasetMetadata) -> None:
                """Register metadata."""

            async def get(self, dataset_id: str) -> ODGDatasetMetadata | None:
                return None

            async def search(self, query: str, limit: int = 20) -> list[ODGDatasetMetadata]:
                return []

        catalog: MetadataCatalog = FakeCatalog()  # type assignment proves structural compat
        assert callable(catalog.register)
        assert callable(catalog.get)
        assert callable(catalog.search)

    def test_module_re_export(self) -> None:
        """MetadataCatalog is re-exported from metadata __init__."""
        from odg_core.metadata import MetadataCatalog as MetaCatalog

        assert MetaCatalog is MetadataCatalog
