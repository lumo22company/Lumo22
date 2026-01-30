"""
AI-powered lead qualification service using OpenAI.
Analyzes leads and provides qualification scores and insights.
"""
import os
from typing import Dict, Any, Optional
from openai import OpenAI
from config import Config

class AIQualifier:
    """AI qualification engine for leads"""
    
    def __init__(self):
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")
        
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL
    
    def qualify_lead(
        self,
        name: str,
        email: str,
        phone: str,
        service_type: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Qualify a lead using AI analysis.
        
        Returns:
            dict with qualification_score (0-100) and qualification_details
        """
        
        prompt = self._build_qualification_prompt(
            name, email, phone, service_type, message
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert lead qualification assistant for service businesses. 
                        Analyze leads and provide a qualification score (0-100) based on:
                        1. Budget indicators (explicit mentions, urgency, service type)
                        2. Intent level (ready to book, researching, just browsing)
                        3. Service fit (does the request match typical service offerings)
                        4. Contact quality (complete information, professional tone)
                        5. Urgency (time-sensitive needs, deadlines mentioned)
                        
                        Respond ONLY with valid JSON in this exact format:
                        {
                            "qualification_score": 75,
                            "budget_estimate": "high|medium|low|unknown",
                            "intent_level": "ready|researching|browsing",
                            "urgency": "high|medium|low",
                            "service_fit": "excellent|good|fair|poor",
                            "reasoning": "Brief explanation of the score",
                            "recommended_action": "auto_book|follow_up|nurture|disqualify"
                        }"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            import json
            qualification_data = json.loads(result)
            
            # Ensure score is within 0-100 range
            score = max(0, min(100, int(qualification_data.get('qualification_score', 0))))
            
            return {
                'qualification_score': score,
                'budget_estimate': qualification_data.get('budget_estimate', 'unknown'),
                'intent_level': qualification_data.get('intent_level', 'researching'),
                'urgency': qualification_data.get('urgency', 'low'),
                'service_fit': qualification_data.get('service_fit', 'fair'),
                'reasoning': qualification_data.get('reasoning', ''),
                'recommended_action': qualification_data.get('recommended_action', 'follow_up')
            }
            
        except Exception as e:
            # Fallback to basic qualification if AI fails
            print(f"AI qualification error: {e}")
            return self._fallback_qualification(message, service_type)
    
    def _build_qualification_prompt(
        self,
        name: str,
        email: str,
        phone: str,
        service_type: str,
        message: str
    ) -> str:
        """Build the qualification prompt"""
        return f"""Analyze this lead for qualification:

Name: {name}
Email: {email}
Phone: {phone}
Service Type: {service_type}
Message: {message}

Provide a qualification analysis with score and recommendations."""
    
    def _fallback_qualification(self, message: str, service_type: str) -> Dict[str, Any]:
        """Basic qualification when AI is unavailable"""
        score = 50  # Default medium score
        
        # Simple keyword-based scoring
        message_lower = message.lower()
        
        # Budget indicators
        if any(word in message_lower for word in ['budget', 'price', 'cost', 'afford', 'quote']):
            score += 10
        
        # Urgency indicators
        if any(word in message_lower for word in ['urgent', 'asap', 'soon', 'immediately', 'this week']):
            score += 15
        
        # Intent indicators
        if any(word in message_lower for word in ['book', 'schedule', 'appointment', 'available', 'when']):
            score += 15
        
        # Service fit (basic check)
        if service_type and len(service_type) > 2:
            score += 10
        
        score = min(100, score)
        
        return {
            'qualification_score': score,
            'budget_estimate': 'unknown',
            'intent_level': 'researching',
            'urgency': 'medium',
            'service_fit': 'fair',
            'reasoning': 'Basic qualification (AI unavailable)',
            'recommended_action': 'follow_up'
        }
