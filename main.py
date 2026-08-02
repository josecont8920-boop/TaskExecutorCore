import json
from core.orchestrator import Orchestrator

if __name__ == "__main__":
    orchestrator = Orchestrator(validate_real=False)
    
    tasks = [
        {
            "id": "task_001",
            "profile_name": "buyer_1",
            "url": "https://httpbin.org/status/200",
            "store_type": "shopify",
            "critical": True,
            "data": {
                "product_id": "12345",
                "quantity": 1,
                "variant_id": "67890"
            }
        },
        {
            "id": "task_002",
            "profile_name": "buyer_2",
            "url": "https://httpbin.org/status/200",
            "store_type": "woocommerce",
            "critical": False,
            "data": {
                "product_id": "45678",
                "quantity": 2
            }
        }
    ]
    
    results = orchestrator.run_flow(tasks)
    print(f"\n✅ Resumen: {results['successful']}/{results['total_tasks']} tareas exitosas")
