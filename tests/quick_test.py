"""
Quick Test Script for AgroSense Crew
Minimal test to verify crew setup works
"""

import logging
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Now your imports will work
from src.agrosense.crew import AgroSenseCrew

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def quick_test():
    """Quick smoke test"""
    logger.info("🚀 Starting AgroSense Crew Quick Test")
    
    # Initialize crew
    crew_instance = AgroSenseCrew()
    logger.info("✅ Crew initialized successfully")
    
    # Generate session
    session_id = crew_instance.mcp_client.generate_session_id()
    logger.info(f"✅ Session ID generated: {session_id}")
    
    # Create context
    query = "My maize has white spots"
    region = "Eldoret"
    
    crew_instance.mcp_client.create_session(
        session_id=session_id,
        query=query,
        region=region
    )
    logger.info("✅ MCP context created")
    
    # Prepare inputs
    inputs = {
        'query': query,
        'region': region,
        'session_id': session_id
    }
    
    logger.info("\n" + "="*60)
    logger.info("Running Crew Workflow")
    logger.info("="*60)
    
    # Run crew
    result = crew_instance.crew().kickoff(inputs=inputs)
    
    logger.info("\n" + "="*60)
    logger.info("✅ CREW EXECUTION COMPLETED!")
    logger.info("="*60)
    
    # Show results
    logger.info(f"\n📊 Result:\n{result}\n")
    
    # Show final context
    final_context = crew_instance.mcp_client.get_context(session_id)
    if final_context:
        logger.info("📋 Final Context State:")
        logger.info(f"  Asset: {final_context.asset_type.value} - {final_context.asset_name}")
        logger.info(f"  Intent: {final_context.intent.value}")
        logger.info(f"  Docs Retrieved: {len(final_context.retrieved_context)}")
        logger.info(f"  Alert Triggered: {final_context.alert_triggered}")
    
    logger.info("\n✅ Quick test completed successfully!")

if __name__ == "__main__":
    quick_test()