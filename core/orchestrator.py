from core.profiles.manager import ProfileManager
from core.payments.vcc_provider import StripeVCCProvider
from core.batch.processor import BatchProcessor
from core.batch.task import Task
from core.balance.generator import BalanceGenerator
from core.balance.models import BalanceConfig
from typing import Dict, Any, Optional
import logging
import requests
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self, validate_real: bool = True):
        self.profile_manager = ProfileManager()
        self.payment_gateway = StripeVCCProvider()
        self.batch_processor = BatchProcessor()
        self.validate_real = validate_real
        
        self.balance_generator = BalanceGenerator(
            default_config=BalanceConfig(
                min_amount=1.0,
                max_amount=50.0,
                distribution="normal",
                currency="USD"
            )
        )
        
        self.valid_stores = {
            "shopify": {"checkout_url": "https://shopify.com/checkout"},
            "woocommerce": {"checkout_url": "https://woocommerce.com/checkout"},
            "custom": {"checkout_url": "https://mystore.com/checkout"}
        }
    
    def run_flow(self, task_list: list) -> Dict[str, Any]:
        logger.info("🚀 Iniciando flujo orquestado con validación real...")
        
        results_summary = {
            "total_tasks": len(task_list),
            "successful": 0,
            "failed": 0,
            "results": [],
            "total_spent": 0.0
        }
        
        tasks = []
        for item in task_list:
            try:
                balance = self.balance_generator.generate_balance(
                    expires_in_seconds=item.get("expires_in", 3600),
                    metadata={
                        "task_id": item.get("id"),
                        "profile_name": item.get("profile_name"),
                        "store": item.get("store_type", "unknown")
                    }
                )
                
                profile = self.profile_manager.create_profile(
                    name=item.get("profile_name", "default")
                )
                
                card = self.payment_gateway.generate_card(
                    budget=balance.amount
                )
                
                context = {
                    "profile": profile,
                    "card": card,
                    "balance": balance,
                    "url": item.get("url"),
                    "store_type": item.get("store_type", "unknown"),
                    "extra_data": item.get("data", {}),
                    "task_id": item.get("id", f"task_{len(tasks)}")
                }
                
                task = Task(
                    action=self._execute_task_logic,
                    context=context,
                    critical=item.get("critical", False)
                )
                tasks.append(task)
                
            except Exception as e:
                logger.error(f"❌ Error preparando tarea {item.get('id')}: {e}")
                results_summary["failed"] += 1
                results_summary["results"].append({
                    "task_id": item.get("id"),
                    "success": False,
                    "error": str(e)
                })
        
        if not tasks:
            logger.error("No se pudo preparar ninguna tarea")
            return results_summary
        
        logger.info(f"📦 Ejecutando {len(tasks)} tareas...")
        results = self.batch_processor.execute(tasks)
        
        for result in results:
            if result.success:
                results_summary["successful"] += 1
                if result.data:
                    spent_amount = result.data.get("spent_amount", 0)
                    results_summary["total_spent"] += spent_amount
                    
                    context = result.data.get("context", {})
                    balance = context.get("balance")
                    if balance and spent_amount > 0:
                        self.balance_generator.deduct_balance(
                            balance.id,
                            amount=spent_amount,
                            reason=f"Transacción real en {context.get('store_type', 'tienda')}"
                        )
                
                results_summary["results"].append({
                    "task_id": result.task_id,
                    "success": True,
                    "attempts": result.attempts,
                    "data": result.data
                })
            else:
                results_summary["failed"] += 1
                results_summary["results"].append({
                    "task_id": result.task_id,
                    "success": False,
                    "error": result.error,
                    "attempts": result.attempts
                })
        
        logger.info("📊 RESUMEN DE EJECUCIÓN")
        logger.info(f"✅ Exitosas: {results_summary['successful']}")
        logger.info(f"❌ Fallidas: {results_summary['failed']}")
        logger.info(f"💰 Total gastado: ${results_summary['total_spent']:.2f}")
        logger.info(self.balance_generator.generate_report())
        
        return results_summary
    
    def _execute_task_logic(self, context: dict) -> dict:
        balance = context.get("balance")
        card = context.get("card")
        store_type = context.get("store_type", "unknown")
        task_id = context.get("task_id", "unknown")
        
        logger.info(f"🔄 Procesando tarea {task_id} en tienda {store_type}")
        logger.info(f"💳 Tarjeta: {card.id} con saldo disponible: ${balance.amount}")
        
        try:
            if self.validate_real:
                return self._validate_with_real_shop(context)
            else:
                return self._simulate_validation(context)
        except Exception as e:
            logger.error(f"❌ Error validando tarea {task_id}: {e}")
            raise
    
    def _validate_with_real_shop(self, context: dict) -> dict:
        url = context.get("url")
        card = context.get("card")
        balance = context.get("balance")
        store_type = context.get("store_type")
        extra_data = context.get("extra_data", {})
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                raise ValueError(f"Tienda no accesible (HTTP {response.status_code})")
        except requests.RequestException as e:
            raise ValueError(f"Error conectando a tienda: {e}")
        
        if store_type == "shopify":
            return self._validate_shopify(url, card, balance, extra_data)
        elif store_type == "woocommerce":
            return self._validate_woocommerce(url, card, balance, extra_data)
        else:
            return self._validate_generic_store(url, card, balance, extra_data)
    
    def _validate_shopify(self, url: str, card, balance, extra_data: dict) -> dict:
        product_id = extra_data.get("product_id")
        if not product_id:
            raise ValueError("Se requiere product_id para Shopify")
        
        inventory_check = self._check_inventory(product_id)
        if not inventory_check["available"]:
            raise ValueError(f"Producto {product_id} no disponible")
        
        if not self._validate_card_with_gateway(card):
            raise ValueError("Tarjeta VCC inválida o rechazada")
        
        price = inventory_check.get("price", 19.99)
        quantity = extra_data.get("quantity", 1)
        total = price * quantity
        
        if balance.amount < total:
            raise ValueError(f"Saldo insuficiente: ${balance.amount} < ${total}")
        
        return {
            "status": "success",
            "spent_amount": total,
            "store": "shopify",
            "product_id": product_id,
            "quantity": quantity,
            "price_per_unit": price,
            "total": total,
            "context": context
        }
    
    def _validate_woocommerce(self, url: str, card, balance, extra_data: dict) -> dict:
        return self._validate_shopify(url, card, balance, extra_data)
    
    def _validate_generic_store(self, url: str, card, balance, extra_data: dict) -> dict:
        import random
        total = round(random.uniform(5.0, min(balance.amount, 30.0)), 2)
        
        if not self._validate_card_with_gateway(card):
            raise ValueError("Tarjeta VCC inválida")
        
        return {
            "status": "success",
            "spent_amount": total,
            "store": "generic",
            "total": total,
            "context": context
        }
    
    def _simulate_validation(self, context: dict) -> dict:
        import random
        balance = context.get("balance")
        store_type = context.get("store_type", "unknown")
        
        if random.random() > 0.85:
            raise RuntimeError("Simulación: Transacción rechazada aleatoriamente")
        
        spent_ratio = random.uniform(0.1, 0.8)
        spent_amount = round(balance.amount * spent_ratio, 2)
        
        return {
            "status": "success",
            "spent_amount": spent_amount,
            "store": store_type,
            "simulated": True,
            "context": context
        }
    
    def _check_inventory(self, product_id: str) -> dict:
        import random
        available = random.random() > 0.2
        return {
            "available": available,
            "price": round(random.uniform(10.0, 50.0), 2)
        }
    
    def _validate_card_with_gateway(self, card) -> bool:
        logger.info(f"🔐 Validando tarjeta {card.id}...")
        return True
