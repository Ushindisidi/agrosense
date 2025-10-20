"""
AgroSense Crew Test Runner
Tests the full multi-agent workflow with MCP state management
"""

import os
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path if needed
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.agrosense.crew import AgroSenseCrew

def test_crew_basic():
    """Basic test with a simple maize disease query"""
    logger.info("=" * 80)
    logger.info("TEST 1: Basic Maize Disease Query")
    logger.info("=" * 80)
    
    crew = AgroSenseCrew()
    
    # Generate session ID
    session_id = crew.mcp_client.generate_session_id()
    logger.info(f"Generated Session ID: {session_id}")
    
    # Create initial context
    query = "My maize leaves have white spots and are turning yellow in Eldoret"
    region = "Eldoret"
    
    context = crew.mcp_client.create_session(
        session_id=session_id,
        query=query,
        region=region
    )
    logger.info(f"Initial context created: {context.query} | {context.region}")
    
    # Prepare inputs for crew
    inputs = {
        'query': query,
        'region': region,
        'session_id': session_id
    }
    
    logger.info("\n🚀 Starting crew execution...")
    
    try:
        # Run the crew
        result = crew.crew().kickoff(inputs=inputs)
        
        logger.info("\n" + "=" * 80)
        logger.info("CREW EXECUTION COMPLETED")
        logger.info("=" * 80)
        
        # Display results
        logger.info(f"\n📊 Final Result:\n{result}")
        
        # Check MCP context state
        final_context = crew.mcp_client.get_context(session_id)
        if final_context:
            logger.info("\n" + "=" * 80)
            logger.info("MCP CONTEXT FINAL STATE")
            logger.info("=" * 80)
            logger.info(crew.mcp_client.get_full_context_summary(session_id))
            
            logger.info(f"\n✅ Asset Type: {final_context.asset_type.value}")
            logger.info(f"✅ Asset Name: {final_context.asset_name}")
            logger.info(f"✅ Intent: {final_context.intent.value}")
            logger.info(f"✅ Documents Retrieved: {len(final_context.retrieved_context)}")
            logger.info(f"✅ Regional Data Keys: {list(final_context.regional_data.keys())}")
            logger.info(f"✅ Alert Triggered: {final_context.alert_triggered}")
            
            if final_context.final_diagnosis and final_context.final_diagnosis != "Diagnosis pending.":
                logger.info(f"\n📋 Final Diagnosis Preview:")
                preview = final_context.final_diagnosis[:500]
                logger.info(preview + ("..." if len(final_context.final_diagnosis) > 500 else ""))
        
        # Check output files
        if os.path.exists('final_diagnosis.txt'):
            logger.info("\n📄 Output file 'final_diagnosis.txt' created successfully")
        if os.path.exists('alert_status.txt'):
            logger.info("📄 Output file 'alert_status.txt' created successfully")
        
        return result
        
    except Exception as e:
        logger.error(f"\n❌ Crew execution failed: {e}", exc_info=True)
        raise

def test_crew_livestock():
    """Test with livestock query"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Livestock Query")
    logger.info("=" * 80)
    
    crew = AgroSenseCrew()
    session_id = crew.mcp_client.generate_session_id()
    
    query = "My dairy cows are not eating well and milk production has dropped"
    region = "Nakuru"
    
    crew.mcp_client.create_session(
        session_id=session_id,
        query=query,
        region=region
    )
    
    inputs = {
        'query': query,
        'region': region,
        'session_id': session_id
    }
    
    logger.info(f"🐄 Testing livestock query: {query}")
    
    try:
        result = crew.crew().kickoff(inputs=inputs)
        
        final_context = crew.mcp_client.get_context(session_id)
        if final_context:
            logger.info(f"\n✅ Asset Type: {final_context.asset_type.value}")
            logger.info(f"✅ Asset Name: {final_context.asset_name}")
            logger.info(f"✅ Intent: {final_context.intent.value}")
        
        logger.info(f"\n✅ Livestock test completed successfully")
        return result
    except Exception as e:
        logger.error(f"❌ Livestock test failed: {e}", exc_info=True)
        raise

def test_crew_market_query():
    """Test with market/pricing query"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Market Price Query")
    logger.info("=" * 80)
    
    crew = AgroSenseCrew()
    session_id = crew.mcp_client.generate_session_id()
    
    query = "What is the current price of tomatoes? Should I sell now?"
    region = "Nairobi"
    
    crew.mcp_client.create_session(
        session_id=session_id,
        query=query,
        region=region
    )
    
    inputs = {
        'query': query,
        'region': region,
        'session_id': session_id
    }
    
    logger.info(f"💰 Testing market query: {query}")
    
    try:
        result = crew.crew().kickoff(inputs=inputs)
        
        final_context = crew.mcp_client.get_context(session_id)
        if final_context:
            logger.info(f"\n✅ Asset Type: {final_context.asset_type.value}")
            logger.info(f"✅ Intent: {final_context.intent.value}")
            if final_context.regional_data:
                logger.info(f"✅ Market Data Retrieved: {bool(final_context.regional_data.get('market_prices'))}")
        
        logger.info(f"\n✅ Market test completed successfully")
        return result
    except Exception as e:
        logger.error(f"❌ Market test failed: {e}", exc_info=True)
        raise

def test_mcp_client_standalone():
    """Test MCP client independently"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: MCP Client Standalone")
    logger.info("=" * 80)
    
    from src.agrosense.core.mcp_client import MCPClient
    from src.agrosense.core.schemas import AssetType, IntentType, Severity, SourceDocument
    
    client = MCPClient()
    session_id = client.generate_session_id()
    
    # Create session
    context = client.create_session(
        session_id=session_id,
        query="Test query for MCP validation",
        region="Test Region"
    )
    logger.info(f"✅ Session created: {session_id}")
    logger.info(f"   Query: {context.query}")
    logger.info(f"   Region: {context.region}")
    logger.info(f"   Default Asset Type: {context.asset_type.value}")
    logger.info(f"   Default Intent: {context.intent.value}")
    
    # Update context with various fields
    client.update_context(
        session_id,
        asset_type="CROP",
        asset_name="maize",
        intent="disease_diagnosis"
    )
    logger.info("✅ Context updated with asset and intent")
    
    # Verify updates
    updated_context = client.get_context(session_id)
    logger.info(f"   Asset Type: {updated_context.asset_type.value}")
    logger.info(f"   Asset Name: {updated_context.asset_name}")
    logger.info(f"   Intent: {updated_context.intent.value}")
    
    # Add mock retrieved documents
    mock_docs = [
        SourceDocument(
            content="Mock content about maize diseases and leaf yellowing symptoms.",
            source="Test_Maize_Manual.pdf",
            page=1,
            asset_type=AssetType.CROP,
            score=0.95
        ),
        SourceDocument(
            content="Additional mock content about nitrogen deficiency in maize.",
            source="Test_Crop_Nutrition.pdf",
            page=12,
            asset_type=AssetType.CROP,
            score=0.87
        )
    ]
    client.update_context(session_id, retrieved_context=mock_docs)
    logger.info(f"✅ Retrieved documents added: {len(mock_docs)} documents")
    
    # Add regional data
    regional_data = {
        "weather": {
            "current": {"temp": 25, "humidity": 70, "rainfall": 5},
            "forecast": ["Sunny", "Partly Cloudy", "Rain Expected"],
            "alerts": []
        },
        "market_prices": {
            "maize": 300,
            "trend": "stable"
        }
    }
    client.update_context(session_id, regional_data=regional_data)
    logger.info("✅ Regional data added")
    logger.info(f"   Weather Keys: {list(regional_data['weather'].keys())}")
    logger.info(f"   Market Keys: {list(regional_data['market_prices'].keys())}")
    
    # Add diagnosis
    diagnosis = "Test diagnosis: The maize crop shows signs of nitrogen deficiency..."
    client.update_context(session_id, final_diagnosis=diagnosis)
    logger.info("✅ Final diagnosis added")
    
    # Add alert info
    client.update_context(
        session_id,
        alert_triggered=True,
        alert_severity=Severity.MEDIUM,
        alert_payload_detail={
            "severity": "MEDIUM",
            "region": "Test Region",
            "asset_type": "CROP",
            "message": "Test alert message"
        }
    )
    logger.info("✅ Alert information added")
    
    # Get summary
    summary = client.get_full_context_summary(session_id)
    logger.info(f"\n📊 Context Summary:\n{summary}")
    
    # Verify all fields
    final_context = client.get_context(session_id)
    logger.info("\n🔍 Final Context Validation:")
    logger.info(f"   ✅ Session ID: {final_context.session_id}")
    logger.info(f"   ✅ Query: {final_context.query}")
    logger.info(f"   ✅ Region: {final_context.region}")
    logger.info(f"   ✅ Asset: {final_context.asset_type.value} - {final_context.asset_name}")
    logger.info(f"   ✅ Intent: {final_context.intent.value}")
    logger.info(f"   ✅ Retrieved Docs: {len(final_context.retrieved_context)}")
    logger.info(f"   ✅ Regional Data: {bool(final_context.regional_data)}")
    logger.info(f"   ✅ Diagnosis: {bool(final_context.final_diagnosis != 'Diagnosis pending.')}")
    logger.info(f"   ✅ Alert Triggered: {final_context.alert_triggered}")
    logger.info(f"   ✅ Alert Severity: {final_context.alert_severity.value if final_context.alert_severity else 'None'}")
    
    # Clean up
    client.clear_session(session_id)
    logger.info("\n✅ Session cleared successfully")
    
    # Verify cleanup
    cleared_context = client.get_context(session_id)
    if cleared_context is None:
        logger.info("✅ Session properly removed from memory")
    else:
        logger.warning("⚠️  Session still exists after clear")

def main():
    """Run all tests"""
    logger.info("\n" + "=" * 80)
    logger.info("AGROSENSE CREW TEST SUITE")
    logger.info("=" * 80)
    
    # Check environment variables
    logger.info("\n🔍 Checking environment variables...")
    required_vars = {
        'PINECONE_API_KEY': 'RAG Tool',
        'PINECONE_ENVIRONMENT': 'RAG Tool',
        'PINECONE_INDEX_NAME': 'RAG Tool',
        'COHERE_API_KEY': 'RAG Tool',
        'N8N_WEBHOOK_URL': 'Alert Tool',
        'GOOGLE_API_KEY': 'Gemini LLM'
    }
    
    missing_vars = []
    for var, tool in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"{var} ({tool})")
            logger.warning(f"⚠️  Missing: {var} - needed for {tool}")
        else:
            logger.info(f"✅ {var} - configured")
    
    if missing_vars:
        logger.warning(f"\n⚠️  Missing {len(missing_vars)} environment variables")
        logger.warning("⚠️  Will run in MOCK mode for affected tools")
    else:
        logger.info("\n✅ All environment variables configured")
    
    tests = [
        ("MCP Client Standalone", test_mcp_client_standalone),
        ("Basic Maize Disease Query", test_crew_basic),
        ("Livestock Query", test_crew_livestock),
        ("Market Price Query", test_crew_market_query)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            logger.info(f"\n{'='*80}")
            logger.info(f"🧪 Running: {test_name}")
            logger.info(f"{'='*80}")
            result = test_func()
            results[test_name] = "✅ PASSED"
        except KeyboardInterrupt:
            logger.warning(f"\n⚠️  Test '{test_name}' interrupted by user")
            results[test_name] = "⚠️  INTERRUPTED"
            break
        except Exception as e:
            results[test_name] = f"❌ FAILED: {str(e)[:100]}"
            logger.error(f"Test '{test_name}' failed: {e}", exc_info=True)
            logger.info("Continuing with next test...")
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    for test_name, result in results.items():
        logger.info(f"{test_name}: {result}")
    
    passed = sum(1 for r in results.values() if "PASSED" in r)
    total = len(results)
    logger.info(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed successfully!")
    elif passed > 0:
        logger.warning(f"⚠️  Some tests failed ({total - passed} failures)")
    else:
        logger.error("❌ All tests failed")
    
    return all("PASSED" in r for r in results.values())

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Test suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)