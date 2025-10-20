import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from src.agrosense.core.mcp_client import MCPClient
    from src.agrosense.core.schemas import AssetType, IntentType, Severity
except ImportError as e:
    print(f"FATAL: Could not import client or schemas. Error: {e}")
    sys.path.pop(0)
    raise

sys.path.pop(0)


class TestMCPClient(unittest.TestCase):
    
    def setUp(self):
        """Set up a fresh MCP client for each test."""
        self.client = MCPClient()
        self.session_id = self.client.generate_session_id()
        self.initial_query = "My maize leaves are yellow in Nakuru."
        self.initial_region = "Nakuru"
        self.client.create_session(self.session_id, self.initial_query, self.initial_region)

    def test_create_and_get_session(self):
        """Test basic session creation and retrieval."""
        context = self.client.get_context(self.session_id)
        self.assertIsNotNone(context)
        self.assertEqual(context.query, self.initial_query)
        self.assertEqual(context.region, self.initial_region)
        self.assertEqual(context.asset_type, AssetType.GENERAL)
        self.assertEqual(context.intent, IntentType.GENERAL_ADVICE)

    def test_update_routing_info_success(self):
        """Test updating fields and checking type conversion (str to Enum)."""
        self.client.update_context(
            self.session_id, 
            asset_type="CROP", 
            asset_name="Maize", 
            intent="disease_diagnosis" 
        )
        context = self.client.get_context(self.session_id)
        self.assertEqual(context.asset_type, AssetType.CROP)
        self.assertEqual(context.asset_name, "Maize")
        self.assertEqual(context.intent, IntentType.DISEASE_DIAGNOSIS)
        
    def test_update_routing_info_fallback(self):
        """Test intent update with a bad string falls back to GENERAL_ADVICE."""
        self.client.update_context(
            self.session_id, 
            intent="bad_unrecognized_intent"
        )
        context = self.client.get_context(self.session_id)
        # Should fallback due to ValueError in IntentType() constructor
        self.assertEqual(context.intent, IntentType.GENERAL_ADVICE)

    def test_update_retrieved_context(self):
        """Test updating with a list of document dicts."""
        doc_data = [{
            "content": "Doc 1 content.",
            "source": "Manual.pdf",
            "page": 1,
            "asset_type": "CROP", 
            "score": 0.99
        }]
        self.client.update_context(
            self.session_id,
            retrieved_context=doc_data
        )
        context = self.client.get_context(self.session_id)
        self.assertEqual(len(context.retrieved_context), 1)
        # Check if the retrieved item is a validated SourceDocument model
        self.assertEqual(context.retrieved_context[0].asset_type, AssetType.CROP)

    def test_get_context_for_task(self):
        """Test output format for agent consumption (Enums as strings/values)."""
        self.client.update_context(self.session_id, asset_type="LIVESTOCK")
        data = self.client.get_context_for_task(self.session_id)
        # Check if Enum values are converted to strings as required by task templates
        self.assertEqual(data['asset_type'], 'LIVESTOCK')
        self.assertIsInstance(data['regional_data'], dict)
        self.assertIn('session_id', data)

    def test_get_full_context_summary(self):
        """Test the string output for agent summary injection."""
        self.client.update_context(self.session_id, asset_name="Potato")
        summary = self.client.get_full_context_summary(self.session_id)
        self.assertIn("Session:", summary)
        self.assertIn("Specific Asset: Potato", summary)
        self.assertIn("Diagnosis Status: PENDING", summary)

if __name__ == '__main__':
    print("--- Running MCPClient Unit Tests ---")
    unittest.main(argv=['first-arg-is-ignored'], exit=False)