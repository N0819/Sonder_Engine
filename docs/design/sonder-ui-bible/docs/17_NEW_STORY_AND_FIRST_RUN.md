# 17. New Story and First Run

## First-run goal

A new user should reach a meaningful story start without first understanding Sonder's internal data model.

## Unified new-story setup

The flow has three equal starting routes:

1. **Describe a story**
2. **Use my Library**
3. **Start blank**

The recommended route may receive a subtle accent edge and short "Recommended" label. The alternatives must not look disabled or secondary in capability.

## Route 1: Describe a story

Use plain prompts to gather:

- story premise;
- player identity/persona;
- important characters;
- optional tone or boundaries;
- optional lore or world details.

Generation should produce ordinary reusable Library records. It must not create a hidden simplified data model.

AI connectivity is checked only when generation is requested. If no provider is connected, offer:

- Connect AI;
- switch to Use my Library;
- switch to Start blank.

Do not block the entire setup at the first screen.

## Route 2: Use my Library

Allow the user to:

- choose a persona;
- select characters;
- attach lore;
- mix existing and newly generated or newly created material;
- review story associations before creation.

Search and filters should remain available without leaving the flow.

## Route 3: Start blank

Ask only for what is required to create the story. Open Play with a clear onboarding checklist or contextual next steps.

Starting blank should feel intentional, not like bypassing the "real" setup.

## Step structure

- Show progress using plain step names, not only numbers.
- Save setup state as a local draft.
- Allow Back without losing work.
- Allow exit and resume.
- Explain optional fields.
- Provide a review screen before final creation when multiple records will be created.
- On mobile, use full-screen staged views with sticky Back and Continue actions.

## Review screen

The review screen should show:

- story name and premise;
- player persona;
- selected/generated characters;
- lore associations;
- language and major content choices;
- what will be created in Library;
- any missing AI connection or validation problem.

The primary action must be explicit, such as Create Story, not Continue or Confirm.

## First Play state

After creation:

- open the new story;
- focus the primary next action;
- show a concise checklist only when the story is underconfigured;
- do not cover the transcript with a large onboarding modal;
- allow the checklist to be dismissed and reopened;
- preserve advanced setup in Story Tools.

## Returning users

Returning users should see:

- Resume recent story as the likely primary action;
- New Story as a visible secondary action;
- Library access;
- connection problems only when they affect the chosen action.

## Host setup and sign-in

Authentication surfaces should use the same visual system but remain more solid and calm than Play.

Requirements:

- clear title and purpose;
- one form at a time;
- preserved trusted-action and lockout protections;
- clear connection and retry messages;
- no decorative technical indexing that distracts from account setup;
- password requirements visible before submission when applicable.

## Guest join

Guest join should ask for the code and explain what happens next. After joining, guest Play should use the same reading and composer language as host Play, with only unavailable host tools removed.
