# Overview

This is a unified control interface for an IR Pump-Probe Spectroscopy System built with Python FastAPI backend and React TypeScript frontend. The application controls and synchronizes six electronic components including lasers, oscilloscopes, signal generators, and positioning systems for scientific spectroscopy experiments. The system is designed as a modular monolith with independent device modules that can be easily extended and duplicated for similar laboratory setups.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Framework**: React 18 with TypeScript for type safety
- **UI Library**: Material-UI (MUI) v5 for consistent scientific interface components
- **Routing**: React Router DOM for navigation between device control panels
- **State Management**: Local component state with hooks, no global state management
- **Build Tool**: Vite for fast development and hot module replacement
- **Theme**: Dark theme optimized for laboratory environments

## Backend Architecture
- **Framework**: FastAPI for async REST API with automatic OpenAPI documentation
- **Module System**: Auto-discovery pattern that dynamically loads device modules from `/modules` directory
- **Device Controllers**: Each hardware device has its own controller class with standardized interfaces
- **API Routes**: RESTful endpoints organized by device with `/api/{device_name}` prefix pattern
- **Configuration**: TOML-based hardware configuration for device parameters and connection settings

## Device Control Pattern
- **Modular Design**: Each hardware device is a self-contained module with controller, routes, and API client
- **Standardized Interface**: Common patterns for connect/disconnect, status retrieval, and parameter control
- **Error Handling**: Consistent error responses and logging across all device modules
- **Status Management**: Real-time device status tracking with WebSocket support planned

## Hardware Communication
- **Serial Communication**: PySerial for Arduino MUX and Quantum Composers signal generator
- **USB Devices**: Direct SDK integration for PicoScope and MIRcat laser systems
- **Network Communication**: TCP/IP for Zurich lock-in amplifier via LabOne API
- **TTL Control**: Hardware-level pulse control for Nd:YAG laser synchronization

## Development Architecture
- **Perpetual Development Mode**: System designed for easy duplication and instrument upgrades
- **Hot Reload**: Both frontend and backend support live code updates during development
- **Hardware Simulation**: Mock controllers enable development without physical hardware access
- **Extensibility**: New instruments can be added by following the established module pattern

# External Dependencies

## Frontend Dependencies
- **@mui/material**: Material-UI component library for scientific interface design
- **@mui/icons-material**: Icon set for device control interfaces
- **react-router-dom**: Client-side routing for multi-device navigation
- **axios**: HTTP client for REST API communication with backend
- **@emotion/react & @emotion/styled**: CSS-in-JS styling for MUI components

## Backend Dependencies
- **fastapi**: Modern async web framework for REST API development
- **uvicorn**: ASGI server for running FastAPI applications
- **pydantic**: Data validation and serialization for API request/response models
- **pyserial**: Serial communication library for Arduino and signal generator control
- **pyvisa**: Instrument control library for VISA-compatible devices
- **python-multipart**: Form data parsing for file uploads and complex requests
- **websockets**: WebSocket support for real-time device status updates
- **toml**: Configuration file parsing for hardware parameters

## Hardware SDKs and Drivers
- **PicoSDK**: Official Pico Technology SDK for PicoScope oscilloscope control
- **MIRcat SDK**: Daylight Solutions SDK for quantum cascade laser control
- **LabOne API**: Zurich Instruments Python API for lock-in amplifier communication
- **VISA Runtime**: National Instruments VISA drivers for instrument communication

## Development Tools
- **TypeScript**: Static type checking for frontend code reliability
- **Vite**: Frontend build tool with fast development server and hot reload
- **ESLint**: Code linting for consistent TypeScript/React code quality

## System Requirements
- **Python 3.8+**: Backend runtime environment
- **Node.js 16+**: Frontend development and build environment
- **Windows/Linux**: Cross-platform support with Windows-specific paths for some SDKs
- **USB Drivers**: Device-specific drivers for direct hardware communication