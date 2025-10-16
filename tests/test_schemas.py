import unittest
from datetime import datetime
from pydantic import ValidationError
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from src.agrosense.core.schemas import (
        AssetType, IntentType, Severity, MCPContext, SourceDocument, AutomationPayload, 
        QueryRequest, QueryResponse, IngestionResponse
    )
except ImportError as e:
    print(f"FATAL: Could not import schemas. Error: {e}")
    sys.path.pop(0) 
    raise
sys.path.pop(0)


class TestUpdatedSchemas(unittest.TestCase):
    
    def test_enum_validation_asset_type(self):
        """Test AssetType enum constraints."""
        self.assertEqual(AssetType("CROP"), AssetType.CROP)
        with self.assertRaises(ValueError):
            AssetType("INSECT") 

    def test_enum_validation_intent_type(self):
        """Test IntentType enum constraints."""
        self.assertEqual(IntentType("pest_management"), IntentType.PEST_MANAGEMENT)
        
        self.assertEqual(IntentType("disease_diagnosis"), IntentType.DISEASE_DIAGNOSIS)
        with self.assertRaises(ValueError):
            IntentType("general query")

    def test_source_document_schema(self):
        """Test RAG SourceDocument validation for correct types."""
        data = {
            "content": "Leaf rust treatment is complex.",
            "source": "Maize-Manual.pdf",
            "page": 10,
            "asset_type": AssetType.CROP,
            "score": 0.92
        }
        doc = SourceDocument(**data)
        self.assertIsInstance(doc.asset_type, AssetType)
        self.assertIsInstance(doc.score, float)
        
        with self.assertRaises(ValidationError):
            SourceDocument(content="c", source="s", page=1, asset_type=AssetType.CROP) # Missing score

    def test_mcp_context_initialization(self):
        """Test MCPContext creation with required fields and defaults."""
        context = MCPContext(
            session_id="s123",
            query="When should I plant maize?",
            region="Nakuru"
        )
        self.assertEqual(context.asset_type, AssetType.GENERAL)
        self.assertEqual(context.intent, IntentType.GENERAL_ADVICE)
        self.assertIsInstance(context.timestamp, datetime)
        self.assertFalse(context.alert_triggered)

    def test_mcp_context_full_update(self):
        """Test MCPContext accepting structured data."""
        doc_data = SourceDocument(content="c", source="s", page=1, asset_type=AssetType.CROP, score=0.9)
        context = MCPContext(
            session_id="full-test",
            query="Maize is yellow",
            region="Nakuru",
            asset_type="CROP",
            intent="disease_diagnosis",
            retrieved_context=[doc_data],
            regional_data={"weather": "dry"},
            alert_severity="HIGH"
        )
        self.assertEqual(context.asset_type, AssetType.CROP)
        self.assertEqual(context.intent, IntentType.DISEASE_DIAGNOSIS)
        self.assertEqual(context.alert_severity, Severity.HIGH)
        self.assertEqual(len(context.retrieved_context), 1)

    def test_automation_payload(self):
        """Test the n8n webhook payload schema."""
        payload = AutomationPayload(
            severity=Severity.HIGH,
            region="Nakuru",
            asset_type="CROP",
            message="Fall Armyworm detected, advise immediate spray."
        )
        self.assertEqual(payload.severity, Severity.HIGH)

    def test_api_schemas(self):
        """Test basic API request/response schemas."""
        req = QueryRequest(query="how to plant", region="Kenya")
        self.assertEqual(req.region, "Kenya")
        
        res = QueryResponse(session_id="456", advice="Done.", alert_status="Alert Not Needed")
        self.assertEqual(res.alert_status, "Alert Not Needed")


if __name__ == '__main__':
    print("--- Running SCHEMAS Unit Tests ---")
    unittest.main(argv=['first-arg-is-ignored'], exit=False)