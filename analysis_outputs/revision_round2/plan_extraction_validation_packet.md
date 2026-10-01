# Plan-extraction validation packet (regenerated; 40 random checkpoints; spans in stripped-text line coordinates)

For each: does the extracted assignment match the model's explicitly proposed current plan and its Unassigned list under the stated rules? Mark yes/no.

## minimax-m2.5 P2_018 T11 — label partial_plan, assigned 6, unassigned ['dashboard', 'payments'], flags []

Extracted: {'mobile': 'sp1', 'auth': 'sp2', 'analytics': 'sp3', 'notifs': 'sp4', 'search': 'sp5', 'api': 'sp5'}

Source span (stripped-text lines (5, 12)):
```
|--------|----------|
| Sprint 1 | Mobile App |
| Sprint 2 | User Authentication |
| Sprint 3 | Analytics Module |
| Sprint 4 | Notification Service |
| Sprint 5 | Search Engine, API Gateway |

**Unassigned:** Dashboard UI, Payment System
```

## gemini-2.5-pro P2_037 T6 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'hr': 'fl1', 'finance': 'fl1', 'eng': 'fl2', 'design': 'fl2', 'product': 'fl3', 'legal': 'fl3', 'mktg': 'fl4', 'sales': 'fl5'}

Source span (stripped-text lines (12, 18)):
```
Current Plan:
Floor 1: Human Resources, Finance
Floor 2: Engineering, Design
Floor 3: Product, Legal
Floor 4: Marketing
Floor 5: Sales
Unassigned:
```

## gemini-2.5-pro P2_020 T6 — label partial_plan, assigned 5, unassigned ['dashboard', 'mobile', 'payments'], flags []

Extracted: {'analytics': 'sp1', 'notifs': 'sp2', 'search': 'sp2', 'auth': 'sp3', 'api': 'sp5'}

Source span (stripped-text lines (8, 14)):
```
Current Plan:
Sprint 1: Analytics Module
Sprint 2: Search Engine, Notification Service
Sprint 3: User Authentication
Sprint 4:
Sprint 5: API Gateway
Unassigned: Dashboard UI, Payment System, Mobile App
```

## gemini-2.5-pro P2_020 T20 — label partial_plan, assigned 5, unassigned ['dashboard', 'mobile', 'payments'], flags []

Extracted: {'auth': 'sp1', 'search': 'sp2', 'analytics': 'sp3', 'notifs': 'sp4', 'api': 'sp5'}

Source span (stripped-text lines (12, 18)):
```
Current Plan:
Sprint 1: User Authentication
Sprint 2: Search Engine
Sprint 3: Analytics Module
Sprint 4: Notification Service
Sprint 5: API Gateway
Unassigned: Dashboard UI, Payment System, Mobile App
```

## deepseek-r1 P2_040 T11 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'product': 'fl1', 'legal': 'fl1', 'eng': 'fl2', 'sales': 'fl2', 'hr': 'fl3', 'finance': 'fl3', 'design': 'fl4', 'mktg': 'fl5'}

Source span (stripped-text lines (0, 7)):
```
**Current Plan:**  
Floor 1: Product, Legal  
Floor 2: Engineering, Sales  
Floor 3: Finance, Human Resources  
Floor 4: Design  
Floor 5: Marketing  
Unassigned: None
```

## minimax-m2.5 P2_019 T20 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'notifs': 'sp1', 'mobile': 'sp1', 'search': 'sp2', 'api': 'sp2', 'auth': 'sp3', 'payments': 'sp3', 'analytics': 'sp4', 'dashboard': 'sp4'}

Source span (stripped-text lines (2, 10)):
```
## Final Plan

**Sprint 1:** Mobile App (13), Notification Service (5) = 18 pts
**Sprint 2:** Search Engine (5), API Gateway (8) = 13 pts
**Sprint 3:** User Authentication (8), Payment System (13) = 21 pts
**Sprint 4:** Analytics Module (8), Dashboard UI (13) = 21 pts
**Sprint 5:** (empty) = 0 pts

Unassigned: (none - all 8 features assigned)
```

## gemini-2.5-pro P2_023 T20 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'notifs': 'sp1', 'search': 'sp1', 'auth': 'sp2', 'mobile': 'sp2', 'payments': 'sp3', 'api': 'sp3', 'analytics': 'sp4', 'dashboard': 'sp5'}

Source span (stripped-text lines (6, 12)):
```
Current Plan:
Sprint 1: Notification Service, Search Engine
Sprint 2: Mobile App, User Authentication
Sprint 3: Payment System, API Gateway
Sprint 4: Analytics Module
Sprint 5: Dashboard UI
Unassigned:
```

## deepseek-r1 P2_025 T20 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'elena': 'wk1', 'bob': 'wk1', 'alice': 'wk2', 'hasan': 'wk2', 'frank': 'wk3', 'grace': 'wk4', 'carol': 'wk5', 'david': 'wk5'}

Source span (stripped-text lines (0, 8)):
```
**Final Plan:**  
Week 1: Bob Kumar, Elena Volkov  
Week 2: Alice Chen, Hasan Ali  
Week 3: Frank Osei  
Week 4: Grace Liu  
Week 5: David Park, Carol Santos  

**Unassigned:** None  

```

## minimax-m2.5 P2_015 T6 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'hike': 'day1', 'temple': 'day1', 'walking_tour': 'day2', 'market': 'day2', 'beach': 'day3', 'show': 'day4', 'museum': 'day5', 'food_tour': 'day5'}

Source span (stripped-text lines (2, 9)):
```
Current Plan:
**Day 1**: Temple Visit, Mountain Hike
**Day 2**: Walking Tour, Local Market
**Day 3**: Beach Excursion
**Day 4**: Cultural Show
**Day 5**: Museum Visit, Food Tour

Unassigned: (none)
```

## gpt-4o P2_016 T20 — label partial_plan, assigned 7, unassigned ['museum'], flags []

Extracted: {'temple': 'day1', 'market': 'day2', 'food_tour': 'day2', 'walking_tour': 'day3', 'hike': 'day4', 'show': 'day4', 'beach': 'day5'}

Source span (stripped-text lines (1, 7)):
```
Current Plan:
Day 1: Temple Visit  
Day 2: Local Market, Food Tour  
Day 3: Walking Tour  
Day 4: Cultural Show, Mountain Hike  
Day 5: Beach Excursion  
Unassigned: Museum Visit  
```

## claude-sonnet-4.5 P2_013 T11 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'show': 'day1', 'walking_tour': 'day1', 'market': 'day2', 'temple': 'day2', 'beach': 'day3', 'hike': 'day3', 'museum': 'day4', 'food_tour': 'day5'}

Source span (stripped-text lines (0, 7)):
```
**Current Plan:**
Day 1: Walking Tour, Cultural Show
Day 2: Local Market, Temple Visit
Day 3: Beach Excursion, Mountain Hike
Day 4: Museum Visit
Day 5: Food Tour, [Empty]
Unassigned: None

```

## deepseek-r1 P2_004 T6 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'data_ws': 'mon_am', 'ai_panel': 'mon_am', 'team_bldg': 'mon_pm', 'research': 'mon_pm', 'keynote': 'tue_am', 'product_demo': 'tue_pm', 'networking': 'wed_am', 'closing': 'wed_am'}

Source span (stripped-text lines (0, 6)):
```
Current Plan:
Monday Morning: Data Science Workshop, AI Ethics Panel
Monday Afternoon: Team Building Activity, Research Talks
Tuesday Morning: Keynote Address
Tuesday Afternoon: Product Demo
Wednesday Morning: Closing Remarks, Networking Session
Unassigned: None
```

## minimax-m2.5 P2_023 T6 — label partial_plan, assigned 1, unassigned ['analytics', 'api', 'auth', 'dashboard', 'mobile', 'payments', 'search'], flags ['assigned_and_unassigned']

Extracted: {'notifs': 'sp1'}

Source span (stripped-text lines (27, 38)):
```
**Current Plan:**

| Sprint | Features |
|--------|----------|
| Sprint 1 | Notification Service |
| Sprint 2 | |
| Sprint 3 | |
| Sprint 4 | |
| Sprint 5 | Payment System |

**Unassigned:** User Authentication, Dashboard UI, Payment System (assigned above), Search Engine, Analytics Module, Mobile App, API Gateway

```

## minimax-m2.5 P2_037 T20 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'product': 'fl1', 'legal': 'fl1', 'eng': 'fl2', 'mktg': 'fl3', 'finance': 'fl3', 'sales': 'fl3', 'hr': 'fl4', 'design': 'fl5'}

Source span (stripped-text lines (2, 8)):
```
Current Plan:
Floor 1: Product, Legal
Floor 2: Engineering
Floor 3: Sales, Marketing, Finance
Floor 4: Human Resources
Floor 5: Design
Unassigned: (none)
```

## gpt-4o P2_018 T6 — label partial_plan, assigned 7, unassigned ['analytics'], flags []

Extracted: {'mobile': 'sp1', 'dashboard': 'sp2', 'notifs': 'sp3', 'payments': 'sp3', 'api': 'sp4', 'auth': 'sp5', 'search': 'sp5'}

Source span (stripped-text lines (4, 11)):
```
**Current Plan:**
Sprint 1: Mobile App  
Sprint 2: Dashboard UI  
Sprint 3: Payment System, Notification Service  
Sprint 4: API Gateway  
Sprint 5: User Authentication, Search Engine  
Unassigned: Analytics Module  

```

## claude-sonnet-4.5 P2_029 T20 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'david': 'wk1', 'bob': 'wk1', 'elena': 'wk2', 'grace': 'wk2', 'alice': 'wk3', 'hasan': 'wk3', 'carol': 'wk4', 'frank': 'wk5'}

Source span (stripped-text lines (2, 10)):
```
**Current Plan:**
```
Week 1: Bob Kumar, David Park
Week 2: Elena Volkov, Grace Liu
Week 3: Alice Chen, Hasan Ali
Week 4: Carol Santos
Week 5: Frank Osei
Unassigned: (none)
```
```

## minimax-m2.5 P2_008 T11 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'data_ws': 'mon_am', 'ai_panel': 'mon_am', 'team_bldg': 'mon_pm', 'research': 'mon_pm', 'networking': 'tue_pm', 'keynote': 'tue_pm', 'closing': 'wed_am', 'product_demo': 'wed_am'}

Source span (stripped-text lines (2, 13)):
```
**Current Plan:**

| Time Block | Session 1 | Session 2 |
|------------|-----------|-----------|
| Monday Morning | Data Science Workshop | AI Ethics Panel |
| Monday Afternoon | Team Building Activity | Research Talks |
| Tuesday Morning | (max 1, filled) | |
| Tuesday Afternoon | Keynote Address | Networking Session |
| Wednesday Morning | Product Demo | Closing Remarks |

**Unassigned:** (none)

```

## minimax-m2.5 P2_037 T6 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'hr': 'fl1', 'finance': 'fl1', 'eng': 'fl2', 'design': 'fl2', 'mktg': 'fl3', 'product': 'fl3', 'sales': 'fl3', 'legal': 'fl4'}

Source span (stripped-text lines (2, 8)):
```
Current Plan:
Floor 1: Human Resources, Finance
Floor 2: Engineering, Design
Floor 3: Product, Sales, Marketing
Floor 4: Legal
Floor 5: 
Unassigned: (none)
```

## minimax-m2.5 P2_003 T6 — label complete_plan, assigned 8, unassigned [], flags ['duplicate_placement']

Extracted: {'data_ws': 'mon_am', 'keynote': 'mon_am', 'team_bldg': 'mon_pm', 'networking': 'mon_pm', 'ai_panel': 'tue_am', 'product_demo': 'tue_am', 'closing': 'tue_pm', 'research': 'wed_am'}

Source span (stripped-text lines (2, 11)):
```
**Current Plan:**

| Time Block | Session 1 | Session 2 |
|------------|-----------|-----------|
| Monday Morning | Keynote Address | Data Science Workshop |
| Monday Afternoon | Networking Session | Team Building Activity |
| Tuesday Morning | AI Ethics Panel | Product Demo |
| Tuesday Afternoon | Closing Remarks | — |
| Wednesday Morning | Research Talks | Product Demo |

```

## minimax-m2.5 P2_024 T20 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'analytics': 'sp1', 'search': 'sp1', 'auth': 'sp2', 'dashboard': 'sp2', 'mobile': 'sp2', 'notifs': 'sp3', 'payments': 'sp3', 'api': 'sp3'}

Source span (stripped-text lines (2, 13)):
```
**Current Plan:**

| Sprint | Assigned Features | Story Points |
|--------|-------------------|--------------|
| Sprint 1 | Search Engine, Analytics Module | 5 + 8 = 13 |
| Sprint 2 | User Authentication, Dashboard UI, Mobile App | 8 + 13 + 13 = 34 |
| Sprint 3 | Notification Service, API Gateway, Payment System | 5 + 8 + 13 = 26 |
| Sprint 4 | (empty) | 0 |
| Sprint 5 | (empty) | 0 |

**Unassigned:** (none)

```

## minimax-m2.5 P2_016 T6 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'market': 'day1', 'temple': 'day1', 'beach': 'day2', 'museum': 'day2', 'show': 'day3', 'food_tour': 'day3', 'walking_tour': 'day4', 'hike': 'day5'}

Source span (stripped-text lines (121, 127)):
```
## Current Plan

**Day 1**: Temple Visit, Local Market
**Day 2**: Museum Visit, Beach Excursion
**Day 3**: Cultural Show, Food Tour
**Day 4**: Walking Tour
**Day 5**: Mountain Hike
```

## claude-sonnet-4.5 P2_030 T6 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'elena': 'wk1', 'bob': 'wk1', 'hasan': 'wk2', 'carol': 'wk3', 'alice': 'wk3', 'david': 'wk4', 'frank': 'wk5', 'grace': 'wk5'}

Source span (stripped-text lines (28, 35)):
```
## Current Plan:
```
Week 1: Elena Volkov, Bob Kumar
Week 2: Hasan Ali
Week 3: Alice Chen, Carol Santos
Week 4: David Park
Week 5: Frank Osei, Grace Liu
Unassigned: (none)
```

## gemini-2.5-pro P2_036 T6 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'eng': 'fl1', 'finance': 'fl1', 'sales': 'fl1', 'design': 'fl2', 'legal': 'fl2', 'hr': 'fl3', 'product': 'fl3', 'mktg': 'fl4'}

Source span (stripped-text lines (14, 20)):
```
Current Plan:
Floor 1: Engineering, Sales, Finance
Floor 2: Legal, Design
Floor 3: Human Resources, Product
Floor 4: Marketing
Floor 5:
Unassigned:
```

## minimax-m2.5 P2_020 T20 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'auth': 'sp1', 'api': 'sp1', 'search': 'sp2', 'notifs': 'sp3', 'analytics': 'sp3', 'mobile': 'sp4', 'payments': 'sp5', 'dashboard': 'sp5'}

Source span (stripped-text lines (2, 8)):
```
## Final Plan

**Sprint 1:** API Gateway, User Authentication
**Sprint 2:** Search Engine
**Sprint 3:** Analytics Module, Notification Service
**Sprint 4:** Mobile App
**Sprint 5:** Dashboard UI, Payment System
```

## minimax-m2.5 P2_012 T11 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'show': 'day1', 'museum': 'day1', 'hike': 'day2', 'food_tour': 'day2', 'walking_tour': 'day3', 'market': 'day3', 'temple': 'day4', 'beach': 'day5'}

Source span (stripped-text lines (2, 9)):
```
Current Plan:
Day 1: Museum Visit, Cultural Show
Day 2: Mountain Hike, Food Tour
Day 3: Walking Tour, Local Market
Day 4: Temple Visit
Day 5: Beach Excursion

Unassigned: (none)
```

## claude-sonnet-4.5 P2_040 T20 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'design': 'fl1', 'mktg': 'fl2', 'sales': 'fl2', 'finance': 'fl3', 'product': 'fl3', 'eng': 'fl4', 'legal': 'fl4', 'hr': 'fl5'}

Source span (stripped-text lines (5, 12)):
```
```
Floor 1: Design, [Empty]
Floor 2: Sales, Marketing
Floor 3: Finance, Product
Floor 4: Legal, Engineering  ← VIOLATES CAPACITY
Floor 5: Human Resources, [Empty]

Unassigned: None
```

## claude-sonnet-4.5 P2_001 T20 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'keynote': 'mon_am', 'ai_panel': 'mon_am', 'team_bldg': 'mon_pm', 'networking': 'mon_pm', 'research': 'tue_am', 'product_demo': 'tue_am', 'data_ws': 'tue_pm', 'closing': 'wed_am'}

Source span (stripped-text lines (5, 12)):
```
Current Plan:
Monday Morning: Keynote Address, AI Ethics Panel
Monday Afternoon: Team Building Activity, Networking Session
Tuesday Morning: Product Demo, Research Talks
Tuesday Afternoon: Data Science Workshop
Wednesday Morning: Closing Remarks, Unassigned slot

Unassigned: None
```

## claude-sonnet-4.5 P2_006 T17 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'team_bldg': 'mon_am', 'networking': 'mon_am', 'keynote': 'mon_pm', 'research': 'mon_pm', 'ai_panel': 'tue_am', 'product_demo': 'tue_pm', 'data_ws': 'wed_am', 'closing': 'wed_am'}

Source span (stripped-text lines (27, 37)):
```
**Current Plan:**
```
Monday Morning: Team Building Activity, Networking Session
Monday Afternoon: Research Talks, Keynote Address ⚠️ VIOLATES Constraint #8
Tuesday Morning: AI Ethics Panel, [1 slot empty]
Tuesday Afternoon: Product Demo ⚠️ VIOLATES Constraint #12 (separated from Data Science Workshop)
Wednesday Morning: Closing Remarks, Data Science Workshop ⚠️ VIOLATES Constraint #12 (separated from Product Demo)
```

**Unassigned:** None

```

## deepseek-r1 P2_028 T6 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'alice': 'wk1', 'david': 'wk2', 'frank': 'wk3', 'bob': 'wk3', 'grace': 'wk3', 'carol': 'wk4', 'elena': 'wk5', 'hasan': 'wk5'}

Source span (stripped-text lines (0, 6)):
```
Current Plan:
Week 1: Alice Chen
Week 2: David Park
Week 3: Bob Kumar, Frank Osei, Grace Liu
Week 4: Carol Santos
Week 5: Elena Volkov, Hasan Ali
Unassigned: 
```

## gpt-4o P2_015 T20 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'hike': 'day1', 'temple': 'day1', 'museum': 'day2', 'market': 'day3', 'beach': 'day4', 'walking_tour': 'day4', 'show': 'day5', 'food_tour': 'day5'}

Source span (stripped-text lines (4, 10)):
```
### Final Plan:
Day 1: Temple Visit, Mountain Hike  
Day 2: Museum Visit  
Day 3: Local Market  
Day 4: Beach Excursion, Walking Tour  
Day 5: Cultural Show, Food Tour  
Unassigned: [None]
```

## gpt-4o P2_037 T11 — label partial_plan, assigned 2, unassigned ['design', 'eng', 'finance', 'legal', 'mktg', 'sales'], flags []

Extracted: {'hr': 'fl1', 'product': 'fl3'}

Source span (stripped-text lines (0, 6)):
```
### Updated Plan:
Floor 1: Human Resources  
Floor 2:  
Floor 3: Product  
Floor 4:  
Floor 5:  
Unassigned: Engineering, Marketing, Sales, Finance, Legal, Design  
```

## deepseek-r1 P2_020 T11 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'auth': 'sp1', 'analytics': 'sp1', 'search': 'sp2', 'mobile': 'sp2', 'notifs': 'sp3', 'dashboard': 'sp3', 'api': 'sp4', 'payments': 'sp5'}

Source span (stripped-text lines (0, 6)):
```
Current Plan:
Sprint 1: Analytics Module, User Authentication
Sprint 2: Search Engine, Mobile App
Sprint 3: Dashboard UI, Notification Service
Sprint 4: API Gateway
Sprint 5: Payment System
Unassigned: 
```

## deepseek-r1 P2_021 T17 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'notifs': 'sp1', 'analytics': 'sp1', 'auth': 'sp2', 'search': 'sp2', 'mobile': 'sp3', 'payments': 'sp4', 'dashboard': 'sp5', 'api': 'sp5'}

Source span (stripped-text lines (0, 6)):
```
**Updated Plan (Final, Incorporating All Constraints):**  
Sprint 1: Analytics Module, Notification Service  
Sprint 2: User Authentication, Search Engine  
Sprint 3: Mobile App  
Sprint 4: Payment System  
Sprint 5: API Gateway, Dashboard UI  
Unassigned: (none)  
```

## gemini-2.5-pro P2_011 T11 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'beach': 'day1', 'show': 'day1', 'hike': 'day2', 'food_tour': 'day2', 'museum': 'day3', 'market': 'day3', 'temple': 'day4', 'walking_tour': 'day5'}

Source span (stripped-text lines (2, 8)):
```
Current Plan:
Day 1: Cultural Show, Beach Excursion
Day 2: Mountain Hike, Food Tour
Day 3: Museum Visit, Local Market
Day 4: Temple Visit
Day 5: Walking Tour
Unassigned:
```

## gpt-4o P2_022 T17 — label partial_plan, assigned 4, unassigned ['auth', 'dashboard', 'mobile', 'payments'], flags []

Extracted: {'notifs': 'sp2', 'analytics': 'sp2', 'api': 'sp2', 'search': 'sp3'}

Source span (stripped-text lines (4, 10)):
```
### Current Plan:
Sprint 1:  
Sprint 2: API Gateway, Notification Service, Analytics Module  
Sprint 3: Search Engine  
Sprint 4:  
Sprint 5:  
Unassigned: User Authentication, Dashboard UI, Payment System, Mobile App  
```

## gemini-2.5-pro P2_025 T6 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'alice': 'wk1', 'frank': 'wk1', 'carol': 'wk2', 'bob': 'wk2', 'elena': 'wk3', 'david': 'wk3', 'grace': 'wk4', 'hasan': 'wk5'}

Source span (stripped-text lines (9, 14)):
```
Current Plan:
Week 1: Alice Chen, Frank Osei
Week 2: Carol Santos, Bob Kumar
Week 3: David Park, Elena Volkov
Week 4: Grace Liu
Week 5: Hasan Ali
```

## deepseek-r1 P2_028 T17 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'david': 'wk1', 'grace': 'wk1', 'carol': 'wk2', 'hasan': 'wk2', 'bob': 'wk3', 'elena': 'wk4', 'alice': 'wk5', 'frank': 'wk5'}

Source span (stripped-text lines (0, 7)):
```
**Current Plan:**
Week 1: Grace Liu, David Park  
Week 2: Carol Santos, Hasan Ali  
Week 3: Bob Kumar  
Week 4: Elena Volkov  
Week 5: Alice Chen, Frank Osei  
Unassigned:  

```

## gpt-4o P2_012 T20 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'beach': 'day1', 'food_tour': 'day1', 'museum': 'day2', 'walking_tour': 'day3', 'market': 'day3', 'hike': 'day4', 'show': 'day5', 'temple': 'day5'}

Source span (stripped-text lines (4, 11)):
```
### Final Plan:
Day 1: Food Tour (65 USD), Beach Excursion (60 USD) → Total: 125 USD  
Day 2: Museum Visit (45 USD) → Total: 45 USD  
Day 3: Walking Tour (30 USD), Local Market (20 USD) → Total: 50 USD  
Day 4: Mountain Hike (25 USD) → Total: 25 USD  
Day 5: Temple Visit (15 USD), Cultural Show (80 USD) → Total: 95 USD  

Unassigned: None  
```

## deepseek-r1 P2_019 T11 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'payments': 'sp1', 'dashboard': 'sp1', 'auth': 'sp2', 'mobile': 'sp2', 'notifs': 'sp3', 'api': 'sp3', 'analytics': 'sp4', 'search': 'sp5'}

Source span (stripped-text lines (0, 6)):
```
Current Plan:  
Sprint 1: Dashboard UI, Payment System  
Sprint 2: User Authentication, Mobile App  
Sprint 3: Notification Service, API Gateway  
Sprint 4: Analytics Module  
Sprint 5: Search Engine  
Unassigned: (none)  
```

## claude-sonnet-4.5 P2_005 T11 — label complete_plan, assigned 8, unassigned [], flags []

Extracted: {'keynote': 'mon_am', 'closing': 'mon_am', 'data_ws': 'mon_pm', 'networking': 'mon_pm', 'team_bldg': 'tue_am', 'product_demo': 'tue_am', 'ai_panel': 'tue_pm', 'research': 'wed_am'}

Source span (stripped-text lines (0, 7)):
```
Current Plan:
**Monday Morning**: Keynote Address, Closing Remarks
**Monday Afternoon**: Data Science Workshop, Networking Session
**Tuesday Morning**: Product Demo, Team Building Activity
**Tuesday Afternoon**: AI Ethics Panel
**Wednesday Morning**: Research Talks, [Empty]

**Unassigned**: None
```

