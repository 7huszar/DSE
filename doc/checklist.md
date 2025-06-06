# Checklist

## Data Mock

- [ ] graceful shutdown
- [ ] logging
- [ ] interfaces according to specs
- [ ] integration tests 
- [ ] commented
- [ ] error handling
- [ ] configurable
---
- [ ] sends periodically data
- [ ] reacts to emergency brake
- [ ] tells if emergency brake is in progress
- [ ] select scenario
- [ ] run scenario

## Location Sender

- [ ] graceful shutdown
- [ ] logging
- [ ] interfaces according to specs
- [ ] integration tests
- [ ] commented
- [ ] error handling
- [ ] configurable
---
- [ ] sends data to backend

## Distance Monitor (Vehicle)

- [ ] graceful shutdown
- [ ] logging
- [ ] interfaces according to specs
- [ ] integration tests
- [ ] commented
- [ ] error handling
- [ ] configurable
---
- [ ] sends data to backend
- [ ] triggers emergency brake

## Emergency Brake

- [ ] graceful shutdown
- [ ] logging
- [ ] interfaces according to specs
- [ ] integration tests
- [ ] commented
- [ ] error handling
- [ ] configurable
---
- [ ] http /trigger
- [ ] rabbitmq trigger
- [ ] sends emergency brake trigger to frontend
- [ ] sends emergency brake complete to frontend

## Location Tracker

- [ ] graceful shutdown
- [ ] logging
- [ ] interfaces according to specs
- [ ] integration tests
- [ ] commented
- [ ] error handling
- [ ] configurable
--- 
- [ ] saves data to db
- [ ] query data from db

## Distance Monitor (Backend)
triggers emergency brake
- [ ] graceful shutdown
- [ ] logging
- [ ] interfaces according to specs
- [ ] integration tests
- [ ] commented
- [ ] error handling
- [ ] configurable

## Passenger API

- [ ] graceful shutdown
- [ ] logging
- [ ] interfaces according to specs
- [ ] integration tests
- [ ] commented
- [ ] error handling
- [ ] configurable

## Frontend