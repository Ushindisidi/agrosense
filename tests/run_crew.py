"""
AgroSense Crew CLI Runner
Simple command-line interface to run the crew with custom queries
"""

import argparse
import logging
import sys
from pathlib import Path
from src.agrosense.crew import AgroSenseCrew

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_query(query: str, region: str, verbose: bool = False):
    """Run a single query through the crew"""
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("="*60)
    logger.info("🌾 AgroSense Agricultural Advisory System")
    logger.info("="*60)
    
    # Initialize crew
    logger.info("\n📦 Initializing crew...")
    crew = AgroSenseCrew()
    
    # Create session
    session_id = crew.mcp_client.generate_session_id()
    crew.mcp_client.create_session(
        session_id=session_id,
        query=query,
        region=region
    )
    
    logger.info(f"📝 Query: {query}")
    logger.info(f"📍 Region: {region}")
    logger.info(f"🆔 Session: {session_id[:12]}...")
    
    # Prepare inputs
    inputs = {
        'query': query,
        'region': region,
        'session_id': session_id
    }
    
    logger.info("\n⚙️  Processing... (this may take 1-2 minutes)\n")
    
    try:
        # Run the crew
        result = crew.crew().kickoff(inputs=inputs)
        
        logger.info("\n" + "="*60)
        logger.info("✅ DIAGNOSIS COMPLETE")
        logger.info("="*60)
        
        # Get final context
        context = crew.mcp_client.get_context(session_id)
        
        if context:
            print("\n" + "="*60)
            print("📊 CLASSIFICATION")
            print("="*60)
            print(f"Asset Type: {context.asset_type.value}")
            print(f"Asset Name: {context.asset_name or 'N/A'}")
            print(f"Query Intent: {context.intent.value}")
            
            if context.retrieved_context:
                print("\n" + "="*60)
                print("📚 KNOWLEDGE RETRIEVED")
                print("="*60)
                print(f"Documents Found: {len(context.retrieved_context)}")
                for i, doc in enumerate(context.retrieved_context[:3], 1):
                    print(f"\n{i}. {doc.source} (Page {doc.page})")
                    print(f"   Score: {doc.score:.2f}")
                    print(f"   Preview: {doc.content[:100]}...")
            
            if context.regional_data:
                print("\n" + "="*60)
                print("🌦️  REGIONAL DATA")
                print("="*60)
                if 'weather' in context.regional_data:
                    weather = context.regional_data['weather']
                    print(f"Weather: {weather.get('forecast_summary', 'N/A')}")
                    print(f"Rainfall (24h): {weather.get('last_24h_rainfall_mm', 'N/A')}mm")
                if 'market_prices' in context.regional_data:
                    market = context.regional_data['market_prices']
                    print(f"\nMarket: {market.get('commodity', 'N/A')}")
                    print(f"Price: {market.get('current_price', 'N/A')}")
                    print(f"Trend: {market.get('trend', 'N/A')}")
            
            if context.final_diagnosis and context.final_diagnosis != "Diagnosis pending.":
                print("\n" + "="*60)
                print("💡 DIAGNOSIS & RECOMMENDATIONS")
                print("="*60)
                print(context.final_diagnosis)
            
            if context.alert_triggered:
                print("\n" + "="*60)
                print("🚨 CRITICAL ALERT")
                print("="*60)
                print(f"Severity: {context.alert_severity.value if context.alert_severity else 'N/A'}")
                print("Alert has been sent to agricultural extension officers.")
            
            # Point to output files
            print("\n" + "="*60)
            print("📄 OUTPUT FILES")
            print("="*60)
            if Path('final_diagnosis.txt').exists():
                print("✅ final_diagnosis.txt - Full diagnosis saved")
            if Path('alert_status.txt').exists():
                print("✅ alert_status.txt - Alert status saved")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Error processing query: {e}", exc_info=verbose)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='AgroSense Agricultural Advisory System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic query
  python run_crew.py "My maize has white spots" --region Eldoret
  
  # Livestock query
  python run_crew.py "My cows are not eating well" --region Nakuru
  
  # Market query
  python run_crew.py "Should I sell my tomatoes now?" --region Nairobi
  
  # With verbose logging
  python run_crew.py "When should I plant potatoes?" --region Molo --verbose
        """
    )
    
    parser.add_argument(
        'query',
        type=str,
        help='The farmer\'s question or observation'
    )
    
    parser.add_argument(
        '-r', '--region',
        type=str,
        required=True,
        help='Geographic region (e.g., Eldoret, Nakuru, Nairobi)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.query.strip():
        logger.error("❌ Query cannot be empty")
        return 1
    
    if not args.region.strip():
        logger.error("❌ Region cannot be empty")
        return 1
    
    # Run the query
    success = run_query(
        query=args.query.strip(),
        region=args.region.strip(),
        verbose=args.verbose
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)