# ⚡ LinkPulse: URL Shortener & Analytics Platform

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688?logo=fastapi)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-CDN-38B2AC?logo=tailwind-css)

LinkPulse is a high-performance, self-hosted URL shortener and real-time link analytics platform designed for creating, protecting, and managing short links with sub-50ms HTTP redirection.

---

## 🌐 Live Demo & API Docs

* **Live Platform**: [LinkPulse Live Application](https://linkpulse.app) *(Update with production URL)*
* **Interactive API Documentation**:  (FastAPI OpenAPI UI)

---

## 🎯 Problem Statement

Basic URL shorteners provide little control over where a link leads or who can access it. They offer limited visibility into link traffic and lack administrative tools to respond to expired, overused, or unsafe links.

## 💡 Solution

LinkPulse resolves short links on the server via native HTTP redirects while recording visitor telemetry asynchronously in the background. Link owners can protect destinations with passwords, expiration dates, and click caps, while administrators maintain platform integrity through user suspensions, link deactivation, and domain blocklisting.

---

## ✨ Key Features

* **Instant Shortening**: Custom alias support with Base62 token fallback algorithm.
* **Access Rules & Intercept Gates**: Password protection, expiration dates, and click capacity thresholds.
* **Bulk Processing & Assets**: Drag-and-drop CSV batch import and downloadable server-side QR codes.
* **Deep Telemetry Analytics**: Real-time Chart.js charts for daily click trends, client devices/OS, referrer channels, and offline MaxMind GeoLite2 geographic mapping.
* **Admin Governance Suite**: Instant link deactivation (), user account suspension, and global domain blocklisting.
* **Hardened Security**: Argon2id password hashing, HTTP-Only session cookies, parameterized SQL queries, and SlowAPI rate limiting.

---

## 🛠️ Tech Stack

* **Backend Engine**: Python 3.12, FastAPI, Uvicorn
* **Database & ORM**: MySQL 8, SQLAlchemy 2.0, PyMySQL
* **Frontend UI**: Jinja2 Templates, Vanilla HTML5 / JavaScript (ES6)
* **Styling & Visualization**: Tailwind CSS CDN, Font Awesome CDN, Chart.js CDN
* **Utilities**: Server-side QR generation (), Offline IP Geolocation ( + MaxMind GeoLite2 City )

---

## 🔑 Judge Demo Accounts

| Role | Email | Password | Access Capabilities |
| **Standard User** | maya@example.com  | MayaPass123! | Create links, CSV import, view personal analytics |
| **Administrator** | admin@linkpulse.local | AdminPass123! | Platform governance, user suspension, link deactivation |

---

## 🚀 Quick Start Setup

### 1. Prerequisites & Database
Ensure Python 3.12 and MySQL 8 are installed and running. Create the MySQL database:



### 2. Environment Configuration
Create a  file in the root directory (refer to ):



### 3. Installation & Seeding



### 4. Database Reset (Fresh Start)
To wipe all tables and re-initialize a clean database schema, run:


---


---

## 👥 Team & Contributions

* **Shreya Rawat** (@shreyaRawat12) — Team Lead & DevOps / Infrastructure
* **Piyush Sunori** (@piyush-sunori) — Lead Architect & Database
* **Rishita Gaula** (@rishitagaula7-pixel) — Auth & Security Specialist
* **Prashasti Agarwal** (@prashasti-Ag) — Core Routing Engine
* **Shailender Singh Bisht** (@Shailender-CSE) — Analytics & Frontend Lead
