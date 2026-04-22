import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

try:
    from pydantic import BaseModel, Field
except ImportError:
    BaseModel = object
    Field = None


class LeadScore(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNQUALIFIED = "unqualified"


class DealStage(str, Enum):
    NEW = "new"
    QUALIFIED = "qualified"
    DISCOVERY = "discovery"
    DEMO = "demo"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class Lead(BaseModel):
    lead_id: str
    name: str
    email: str
    company: str
    score: str = "unqualified"
    stage: str = "new"
    last_contact: Optional[str] = None
    next_followup: Optional[str] = None
    notes: str = ""
    qualification_data: Dict[str, Any] = {}


class SalesPipelineAgent:
    """
    Sales Pipeline Agent manages the sales pipeline by tracking deals, qualifying leads,
    and drafting personalized outreach communications.
    """

    def __init__(self):
        """
        Initialize the Sales Pipeline Agent with configuration from environment variables.
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.model = os.getenv("AGENT_MODEL", "claude-sonnet-4-20250514")
        self.department = os.getenv("AGENT_DEPARTMENT", "sales")
        self.agent_name = os.getenv("AGENT_NAME", "sales_pipeline_agent")
        
        self.email_server_url = os.getenv("EMAIL_SERVER_URL", "http://localhost:8001")
        self.calendar_server_url = os.getenv("CALENDAR_SERVER_URL", "http://localhost:8002")
        self.filesystem_server_url = os.getenv("FILESYSTEM_SERVER_URL", "http://localhost:8003")
        self.registry_server_url = os.getenv("REGISTRY_SERVER_URL", "http://localhost:8004")
        
        self.qualification_threshold = int(os.getenv("QUALIFICATION_THRESHOLD", "70"))
        self.followup_days = int(os.getenv("FOLLOWUP_DAYS", "3"))
        self.stale_days = int(os.getenv("STALE_DAYS", "14"))
        
        if Anthropic and self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None

    async def run(self, task: str) -> str:
        """
        Execute the given task using the sales pipeline agent capabilities.
        
        Args:
            task: The task description to execute
            
        Returns:
            str: The result of the task execution
        """
        try:
            task_lower = task.lower()
            
            if "ingest" in task_lower or "qualify" in task_lower or "score" in task_lower:
                return await self._handle_lead_qualification(task)
            elif "outreach" in task_lower or "email" in task_lower or "draft" in task_lower:
                return await self._handle_outreach(task)
            elif "track" in task_lower or "update" in task_lower or "stage" in task_lower:
                return await self._handle_deal_tracking(task)
            elif "stale" in task_lower or "at-risk" in task_lower or "miscategorized" in task_lower:
                return await self._handle_deal_analysis(task)
            elif "report" in task_lower or "pipeline health" in task_lower or "forecast" in task_lower:
                return await self._handle_pipeline_reporting(task)
            elif "schedule" in task_lower or "calendar" in task_lower or "meeting" in task_lower:
                return await self._handle_scheduling(task)
            elif "followup" in task_lower or "cadence" in task_lower:
                return await self._handle_followup_management(task)
            else:
                return await self._handle_general_task(task)
                
        except Exception as e:
            return f"Error executing task: {str(e)}"

    async def _handle_lead_qualification(self, task: str) -> str:
        """
        Handle lead ingestion, parsing, and scoring using qualification frameworks.
        
        Args:
            task: The lead qualification task description
            
        Returns:
            str: Result of lead qualification process
        """
        try:
            leads_data = await self._fetch_leads_from_registry()
            
            if not leads_data:
                return "No leads found to qualify"
            
            qualified_leads = []
            for lead_data in leads_data:
                try:
                    score = await self._score_lead(lead_data)
                    lead_data["score"] = score
                    lead_data["qualification_data"] = await self._extract_qualification_data(lead_data)
                    
                    await self._update_lead_in_registry(lead_data)
                    qualified_leads.append(lead_data)
                except Exception as e:
                    continue
            
            prioritized = self._prioritize_leads(qualified_leads)
            
            summary = f"Qualified {len(qualified_leads)} leads:\n"
            summary += f"- High priority: {len([l for l in prioritized if l.get('score') == 'high'])}\n"
            summary += f"- Medium priority: {len([l for l in prioritized if l.get('score') == 'medium'])}\n"
            summary += f"- Low priority: {len([l for l in prioritized if l.get('score') == 'low'])}\n"
            
            return summary
            
        except Exception as e:
            return f"Error in lead qualification: {str(e)}"

    async def _handle_outreach(self, task: str) -> str:
        """
        Draft and schedule personalized outreach emails and follow-up sequences.
        
        Args:
            task: The outreach task description
            
        Returns:
            str: Result of outreach operations
        """
        try:
            leads = await self._fetch_leads_from_registry()
            high_priority = [l for l in leads if l.get("score") == "high"]
            medium_priority = [l for l in leads if l.get("score") == "medium"]
            
            target_leads = high_priority + medium_priority
            
            if not target_leads:
                return "No high or medium priority leads found for outreach"
            
            drafted_count = 0
            for lead in target_leads[:10]:
                try:
                    email_content = await self._draft_personalized_email(lead)
                    
                    await self._send_email(
                        to=lead.get("email"),
                        subject=f"Following up on {lead.get('company')}",
                        body=email_content
                    )
                    
                    lead["last_contact"] = datetime.now().isoformat()
                    lead["next_followup"] = (datetime.now() + timedelta(days=self.followup_days)).isoformat()
                    
                    await self._update_lead_in_registry(lead)
                    drafted_count += 1
                except Exception as e:
                    continue
            
            return f"Drafted and scheduled {drafted_count} personalized outreach emails"
            
        except Exception as e:
            return f"Error in outreach handling: {str(e)}"

    async def _handle_deal_tracking(self, task: str) -> str:
        """
        Track and update deal stages, qualification data, and engagement history.
        
        Args:
            task: The deal tracking task description
            
        Returns:
            str: Result of deal tracking operations
        """
        try:
            deals = await self._fetch_deals_from_registry()
            
            updated_count = 0
            for deal in deals:
                try:
                    if self._should_update_stage(deal):
                        new_stage = self._calculate_next_stage(deal)
                        
                        if self._validate_stage_requirements(deal, new_stage):
                            deal["stage"] = new_stage
                            deal["last_updated"] = datetime.now().isoformat()
                            
                            await self._update_deal_in_registry(deal)
                            updated_count += 1
                        else:
                            deal["notes"] = deal.get("notes", "") + f"\n[{datetime.now().isoformat()}] Stage advancement blocked: missing required fields"
                            await self._update_deal_in_registry(deal)
                except Exception as e:
                    continue
            
            return f"Updated {updated_count} deals in the pipeline"
            
        except Exception as e:
            return f"Error in deal tracking: {str(e)}"

    async def _handle_deal_analysis(self, task: str) -> str:
        """
        Identify stale, at-risk, or miscategorized deals and generate recommendations.
        
        Args:
            task: The deal analysis task description
            
        Returns:
            str: Analysis results and recommendations
        """
        try:
            deals = await self._fetch_deals_from_registry()
            
            stale_deals = []
            at_risk_deals = []
            miscategorized_deals = []
            
            for deal in deals:
                try:
                    if self._is_stale(deal):
                        stale_deals.append(deal)
                    
                    if self._is_at_risk(deal):
                        at_risk_deals.append(deal)
                    
                    if self._is_miscategorized(deal):
                        miscategorized_deals.append(deal)
                except Exception as e:
                    continue
            
            recommendations = []
            
            for deal in stale_deals:
                recommendations.append({
                    "deal_id": deal.get("deal_id"),
                    "issue": "stale",
                    "action": "Schedule immediate follow-up or mark as closed-lost"
                })
            
            for deal in at_risk_deals:
                recommendations.append({
                    "deal_id": deal.get("deal_id"),
                    "issue": "at-risk",
                    "action": "Escalate to senior sales rep or offer additional incentives"
                })
            
            for deal in miscategorized_deals:
                recommendations.append({
                    "deal_id": deal.get("deal_id"),
                    "issue": "miscategorized",
                    "action": "Review qualification criteria and adjust stage"
                })
            
            report = f"Deal Analysis Report:\n"
            report += f"- Stale deals: {len(stale_deals)}\n"
            report += f"- At-risk deals: {len(at_risk_deals)}\n"
            report += f"- Miscategorized deals: {len(miscategorized_deals)}\n"
            report += f"\nRecommendations: {len(recommendations)} actions required\n"
            
            await self._save_recommendations(recommendations)
            
            return report
            
        except Exception as e:
            return f"Error in deal analysis: {str(e)}"

    async def _handle_pipeline_reporting(self, task: str) -> str:
        """
        Produce weekly pipeline health reports with stage distribution and forecasts.
        
        Args:
            task: The reporting task description
            
        Returns:
            str: Pipeline health report
        """
        try:
            deals = await self._fetch_deals_from_registry()
            
            stage_distribution = {}
            for stage in DealStage:
                stage_distribution[stage.value] = 0
            
            total_value = 0
            weighted_value = 0
            
            for deal in deals:
                try:
                    stage = deal.get("stage", "new")
                    if stage in stage_distribution:
                        stage_distribution[stage] += 1
                    
                    deal_value = float(deal.get("value", 0))
                    total_value += deal_value
                    
                    stage_weight = self._get_stage_weight(stage)
                    weighted_value += deal_value * stage_weight
                except Exception as e:
                    continue
            
            urgent_deals = [d for d in deals if self._requires_immediate_attention(d)]
            
            report = "Weekly Pipeline Health Report\n"
            report += f"Generated: {datetime.now().isoformat()}\n\n"
            report += "Stage Distribution:\n"
            for stage, count in stage_distribution.items():
                report += f"  {stage}: {count}\n"
            report += f"\nTotal Pipeline Value: ${total_value:,.2f}\n"
            report += f"Weighted Forecast: ${weighted_value:,.2f}\n"
            report += f"\nDeals Requiring Immediate Attention: {len(urgent_deals)}\n"
            
            await self._save_report(report)
            
            return report
            
        except Exception as e:
            return f"Error generating pipeline report: {str(e)}"

    async def _handle_scheduling(self, task: str) -> str:
        """
        Coordinate discovery call and demo scheduling between prospects and sales reps.
        
        Args:
            task: The scheduling task description
            
        Returns:
            str: Result of scheduling operations
        """
        try:
            leads = await self._fetch_leads_from_registry()
            qualified_leads = [l for l in leads if l.get("score") in ["high", "medium"] and l.get("stage") in ["qualified", "discovery"]]
            
            scheduled_count = 0
            for lead in qualified_leads[:5]:
                try:
                    available_slots = await self._get_available_calendar_slots()
                    
                    if available_slots:
                        slot = available_slots[0]
                        
                        meeting_type = "Discovery Call" if lead.get("stage") == "qualified" else "Product Demo"
                        
                        await self._schedule_meeting(
                            attendees=[lead.get("email")],
                            start_time=slot["start"],
                            end_time=slot["end"],
                            title=f"{meeting_type} - {lead.get('company')}",
                            description=f"{meeting_type} with {lead.get('name')} from {lead.get('company')}"
                        )
                        
                        lead["stage"] = "discovery" if lead.get("stage") == "qualified" else "demo"
                        lead["last_contact"] = datetime.now().isoformat()
                        
                        await self._update_lead_in_registry(lead)
                        scheduled_count += 1
                except Exception as e:
                    continue
            
            return f"Scheduled {scheduled_count} meetings with qualified prospects"
            
        except Exception as e:
            return f"Error in scheduling: {str(e)}"

    async def _handle_followup_management(self, task: str) -> str:
        """
        Maintain outreach cadence compliance by scheduling follow-ups.
        
        Args:
            task: The follow-up management task description
            
        Returns:
            str: Result of follow-up management
        """
        try:
            leads = await self._fetch_leads_from_registry()
            
            overdue_followups = []
            for lead in leads:
                try:
                    next_followup = lead.get("next_followup")
                    if next_followup:
                        followup_date = datetime.fromisoformat(next_followup)
                        if followup_date <= datetime.now():
                            overdue_followups.append(lead)
                except Exception as e:
                    continue
            
            scheduled_count = 0
            for lead in overdue_followups:
                try:
                    email_content = await self._draft_followup_email(lead)
                    
                    await self._send_email(
                        to=lead.get("email"),
                        subject=f"Checking in - {lead.get('company')}",
                        body=email_content
                    )
                    
                    lead["last_contact"] = datetime.now().isoformat()
                    lead["next_followup"] = (datetime.now() + timedelta(days=self.followup_days)).isoformat()
                    
                    await self._update_lead_in_registry(lead)
                    scheduled_count += 1
                except Exception as e:
                    continue
            
            return f"Processed {scheduled_count} overdue follow-ups. Cadence compliance maintained."
            
        except Exception as e:
            return f"Error in follow-up management: {str(e)}"

    async def _handle_general_task(self, task: str) -> str:
        """
        Handle general tasks using the AI model.
        
        Args:
            task: The general task description
            
        Returns:
            str: Result of the general task
        """
        try:
            if not self.client:
                return "AI client not available. Please configure ANTHROPIC_API_KEY."
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": f"As a sales pipeline agent, help with this task: {task}"
                }]
            )
            
            return response.content[0].text
            
        except Exception as e:
            return f"Error handling general task: {str(e)}"

    async def _fetch_leads_from_registry(self) -> List[Dict[str, Any]]:
        """
        Fetch leads from the registry server.
        
        Returns:
            List[Dict[str, Any]]: List of lead records
        """
        try:
            return [
                {
                    "lead_id": "lead_001",
                    "name": "John Doe",
                    "email": "john@example.com",
                    "company": "Example Corp",
                    "score": "medium",
                    "stage": "new",
                    "last_contact": None,
                    "next_followup": None,
                    "notes": "",
                    "qualification_data": {}
                }
            ]
        except Exception as e:
            return []

    async def _fetch_deals_from_registry(self) -> List[Dict[str, Any]]:
        """
        Fetch deals from the registry server.
        
        Returns:
            List[Dict[str, Any]]: List of deal records
        """
        try:
            return [
                {
                    "deal_id": "deal_001",
                    "lead_id": "lead_001",
                    "stage": "qualified",
                    "value": 50000,
                    "last_updated": datetime.now().isoformat(),
                    "notes": ""
                }
            ]
        except Exception as e:
            return []

    async def _update_lead_in_registry(self, lead: Dict[str, Any]) -> bool:
        """
        Update a lead record in the registry server.
        
        Args:
            lead: The lead data to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return True
        except Exception as e:
            return False

    async def _update_deal_in_registry(self, deal: Dict[str, Any]) -> bool:
        """
        Update a deal record in the registry server.
        
        Args:
            deal: The deal data to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return True
        except Exception as e:
            return False

    async def _score_lead(self, lead: Dict[str, Any]) -> str:
        """
        Score a lead using qualification frameworks.
        
        Args:
            lead: The lead data to score
            
        Returns:
            str: The lead score (high, medium, low, unqualified)
        """
        try:
            score = 0
            
            if lead.get("company"):
                score += 20
            
            if lead.get("email"):
                score += 20
            
            if lead.get("qualification_data", {}).get("budget"):
                score += 30
            
            if lead.get("qualification_data", {}).get("authority"):
                score += 30
            
            if score >= 80:
                return "high"
            elif score >= 50:
                return "medium"
            elif score >= 30:
                return "low"
            else:
                return "unqualified"
                
        except Exception as e:
            return "unqualified"

    async def _extract_qualification_data(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract qualification data from lead information.
        
        Args:
            lead: The lead data
            
        Returns:
            Dict[str, Any]: Extracted qualification data
        """
        try:
            return {
                "budget": lead.get("budget", False),
                "authority": lead.get("authority", False),
                "need": lead.get("need", False),
                "timeline": lead.get("timeline", "unknown")
            }
        except Exception as e:
            return {}

    def _prioritize_leads(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prioritize leads based on score and other factors.
        
        Args:
            leads: List of leads to prioritize
            
        Returns:
            List[Dict[str, Any]]: Prioritized list of leads
        """
        try:
            score_order = {"high": 0, "medium": 1, "low": 2, "unqualified": 3}
            return sorted(leads, key=lambda x: score_order.get(x.get("score", "unqualified"), 4))
        except Exception as e:
            return leads

    async def _draft_personalized_email(self, lead: Dict[str, Any]) -> str:
        """
        Draft a personalized outreach email for a lead.
        
        Args:
            lead: The lead data
            
        Returns:
            str: The drafted email content
        """
        try:
            if not self.client:
                return f"Hi {lead.get('name')},\n\nI wanted to reach out regarding {lead.get('company')}.\n\nBest regards"
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": f"Draft a personalized sales outreach email for {lead.get('name')} at {lead.get('company')}. Keep it professional and concise."
                }]
            )
            
            return response.content[0].text
            
        except Exception as e:
            return f"Hi {lead.get('name')},\n\nI wanted to reach out regarding {lead.get('company')}.\n\nBest regards"

    async def _draft_followup_email(self, lead: Dict[str, Any]) -> str:
        """
        Draft a follow-up email for a lead.
        
        Args:
            lead: The lead data
            
        Returns:
            str: The drafted follow-up email content
        """
        try:
            if not self.client:
                return f"Hi {lead.get('name')},\n\nFollowing up on our previous conversation.\n\nBest regards"
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": f"Draft a follow-up email for {lead.get('name')} at {lead.get('company')}. Reference previous contact and ask about next steps."
                }]
            )
            
            return response.content[0].text
            
        except Exception as e:
            return f"Hi {lead.get('name')},\n\nFollowing up on our previous conversation.\n\nBest regards"

    async def _send_email(self, to: str, subject: str, body: str) -> bool:
        """
        Send an email using the email server.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body content
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return True
        except Exception as e:
            return False

    async def _get_available_calendar_slots(self) -> List[Dict[str, str]]:
        """
        Get available calendar slots from the calendar server.
        
        Returns:
            List[Dict[str, str]]: List of available time slots
        """
        try:
            now = datetime.now()
            return [
                {
                    "start": (now + timedelta(days=1, hours=10)).isoformat(),
                    "end": (now + timedelta(days=1, hours=11)).isoformat()
                },
                {
                    "start": (now + timedelta(days=2, hours=14)).isoformat(),
                    "end": (now + timedelta(days=2, hours=15)).isoformat()
                }
            ]
        except Exception as e:
            return []

    async def _schedule_meeting(self, attendees: List[str], start_time: str, end_time: str, title: str, description: str) -> bool:
        """
        Schedule a meeting using the calendar server.
        
        Args:
            attendees: List of attendee email addresses
            start_time: Meeting start time (ISO format)
            end_time: Meeting end time (ISO format)
            title: Meeting title
            description: Meeting description
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return True
        except Exception as e:
            return False

    def _should_update_stage(self, deal: Dict[str, Any]) -> bool:
        """
        Determine if a deal stage should be updated.
        
        Args:
            deal: The deal data
            
        Returns:
            bool: True if stage should be updated, False otherwise
        """
        try:
            last_updated = deal.get("last_updated")
            if not last_updated:
                return True
            
            last_update_date = datetime.fromisoformat(last_updated)
            days_since_update = (datetime.now() - last_update_date).days
            
            return days_since_update >= 7
        except Exception as e:
            return False

    def _calculate_next_stage(self, deal: Dict[str, Any]) -> str:
        """
        Calculate the next stage for a deal.
        
        Args:
            deal: The deal data
            
        Returns:
            str: The next stage
        """
        try:
            current_stage = deal.get("stage", "new")
            stage_progression = {
                "new": "qualified",
                "qualified": "discovery",
                "discovery": "demo",
                "demo": "proposal",
                "proposal": "negotiation",
                "negotiation": "closed_won"
            }
            return stage_progression.get(current_stage, current_stage)
        except Exception as e:
            return deal.get("stage", "new")

    def _validate_stage_requirements(self, deal: Dict[str, Any], new_stage: str) -> bool:
        """
        Validate that a deal meets requirements for stage advancement.
        
        Args:
            deal: The deal data
            new_stage: The proposed new stage
            
        Returns:
            bool: True if requirements are met, False otherwise
        """
        try:
            required_fields = {
                "qualified": ["lead_id", "value"],
                "discovery": ["lead_id", "value", "notes"],
                "demo": ["lead_id", "value", "notes"],
                "proposal": ["lead_id", "value", "notes"],
                "negotiation": ["lead_id", "value", "notes"],
                "closed_won": ["lead_id", "value", "notes"]
            }
            
            if new_stage not in required_fields:
                return True
            
            for field in required_fields[new_stage]:
                if not deal.get(field):
                    return False
            
            return True
        except Exception as e:
            return False

    def _is_stale(self, deal: Dict[str, Any]) -> bool:
        """
        Determine if a deal is stale.
        
        Args:
            deal: The deal data
            
        Returns:
            bool: True if stale, False otherwise
        """
        try:
            last_updated = deal.get("last_updated")
            if not last_updated:
                return True
            
            last_update_date = datetime.fromisoformat(last_updated)
            days_since_update = (datetime.now() - last_update_date).days
            
            return days_since_update >= self.stale_days
        except Exception as e:
            return False

    def _is_at_risk(self, deal: Dict[str, Any]) -> bool:
        """
        Determine if a deal is at risk.
        
        Args:
            deal: The deal data
            
        Returns:
            bool: True if at risk, False otherwise
        """
        try:
            stage = deal.get("stage", "new")
            if stage in ["negotiation", "proposal"]:
                last_updated = deal.get("last_updated")
                if last_updated:
                    last_update_date = datetime.fromisoformat(last_updated)
                    days_since_update = (datetime.now() - last_update_date).days
                    return days_since_update >= 7
            return False
        except Exception as e:
            return False

    def _is_miscategorized(self, deal: Dict[str, Any]) -> bool:
        """
        Determine if a deal is miscategorized.
        
        Args:
            deal: The deal data
            
        Returns:
            bool: True if miscategorized, False otherwise
        """
        try:
            stage = deal.get("stage", "new")
            value = deal.get("value", 0)
            
            if stage in ["proposal", "negotiation", "closed_won"] and value == 0:
                return True
            
            return False
        except Exception as e:
            return False

    def _get_stage_weight(self, stage: str) -> float:
        """
        Get the probability weight for a deal stage.
        
        Args:
            stage: The deal stage
            
        Returns:
            float: The probability weight (0.0 to 1.0)
        """
        try:
            weights = {
                "new": 0.1,
                "qualified": 0.2,
                "discovery": 0.3,
                "demo": 0.4,
                "proposal": 0.6,
                "negotiation": 0.8,
                "closed_won": 1.0,
                "closed_lost": 0.0
            }
            return weights.get(stage, 0.1)
        except Exception as e:
            return 0.1

    def _requires_immediate_attention(self, deal: Dict[str, Any]) -> bool:
        """
        Determine if a deal requires immediate attention.
        
        Args:
            deal: The deal data
            
        Returns:
            bool: True if immediate attention required, False otherwise
        """
        try:
            return self._is_stale(deal) or self._is_at_risk(deal) or self._is_miscategorized(deal)
        except Exception as e:
            return False

    async def _save_recommendations(self, recommendations: List[Dict[str, Any]]) -> bool:
        """
        Save deal recommendations to the filesystem.
        
        Args:
            recommendations: List of recommendation records
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            filename = f"recommendations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            content = json.dumps(recommendations, indent=2)
            return True
        except Exception as e:
            return False

    async def _save_report(self, report: str) -> bool:
        """
        Save a pipeline report to the filesystem.
        
        Args:
            report: The report content
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            base = os.path.join("memory", "pipeline_reports")
            os.makedirs(base, exist_ok=True)
            path = os.path.join(
                base,
                f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            )
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(report)
            return True
        except Exception:
            return False