# Shmoobox

**Shmoobox** is a self-hosted email appliance designed to run on
Raspberry Pi hardware.

The goal of the project is to make it easy to run a reliable personal
mail server without the complexity normally associated with configuring
mail infrastructure.

Shmoobox combines a standard Linux mail stack with a simple web
interface for setup and management.

------------------------------------------------------------------------

## Project Goals

Shmoobox aims to provide:

-   A **plug-and-play mail server appliance**
-   Simple **web-based configuration**
-   Minimal administration requirements
-   Transparent and auditable infrastructure
-   A system that can run reliably on inexpensive hardware

The project focuses exclusively on **email services** rather than
becoming a general home server platform.

------------------------------------------------------------------------

## Architecture

Shmoobox is built from standard components:

    Browser UI
        ↓
    Flask control interface
        ↓
    Mail services
        - Postfix (SMTP)
        - Dovecot (IMAP)
        - Spam filtering
        - DKIM / TLS
        ↓
    Debian / Raspberry Pi OS

The Flask application acts as the **control layer** that configures and
monitors the underlying mail services.

------------------------------------------------------------------------

## Development Status

This project is currently in **early development**.

Current components include:

-   Raspberry Pi appliance environment
-   Flask web interface
-   systemd service integration
-   automated deployment from development machine

Upcoming work includes:

-   configuration system
-   first-run setup wizard
-   mailbox management
-   DNS configuration guidance
-   mail diagnostics

------------------------------------------------------------------------

## Development Workflow

Development is performed on a separate machine and deployed to the
appliance.

Typical workflow:

    edit code on dev machine
          ↓
    run deploy script
          ↓
    code installed on appliance
          ↓
    service restarted automatically
          ↓
    test in browser

------------------------------------------------------------------------

## Repository Structure

    app/        Flask application
    config/     example configuration files
    deploy/     deployment scripts
    docs/       project documentation

------------------------------------------------------------------------

## License

Shmoobox is released under the **MIT License**.

See the LICENSE file for details.

------------------------------------------------------------------------

## Author

Jeremiah A. Brown
