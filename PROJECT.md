# DataCombiner Project Direction

## Product Thesis

DataCombiner is a lightweight workflow automation tool for churches and small organizations that repeatedly combine weekly spreadsheet exports into a clean master sheet.

The goal is not to replace Excel, Google Sheets, or advanced tools like Power Query. Those tools are powerful, but they are often too technical for nontechnical church staff or volunteers who simply need to combine recurring files accurately.

DataCombiner focuses on a guided workflow:

1. Select weekly files or a Google Drive folder.
2. Detect shared columns across the files.
3. Let the user choose the merge column.
4. Preview the combined result before final output.
5. Show missing values, unmatched rows, and possible data problems clearly.
6. Produce a clean downloadable CSV or update a master Google Sheet.
7. Eventually automate the workflow weekly.

The long-term goal is a one-click or scheduled automation system where a church can select its weekly source files and automatically produce an updated master sheet.

## Target User

The primary user is a nontechnical church admin, ministry coordinator, or volunteer who receives recurring spreadsheet exports from tools such as Google Forms, Google Sheets, attendance systems, or registration forms.

They may understand the church data, but they should not need to understand Power Query, SQL joins, pandas, Apps Script, Zapier, Make, or other automation platforms.

## Problem

Churches and small organizations often collect data through multiple recurring forms or spreadsheet exports.

Examples:

- weekly attendance forms,
- volunteer sign-up forms,
- small group attendance sheets,
- event registration sheets,
- ministry contact lists,
- follow-up forms.

The data may live in separate CSV, XLSX, or Google Sheets files. The person responsible for combining the data may have to manually copy, paste, clean, and compare rows every week.

This is error-prone, repetitive, and difficult for nontechnical users.

## Core Product Idea

DataCombiner should make the recurring workflow simple:

```text
weekly source files
        ↓
detect shared columns
        ↓
choose merge column
        ↓
preview combined data
        ↓
check missing/unmatched values
        ↓
download CSV or update master Google Sheet