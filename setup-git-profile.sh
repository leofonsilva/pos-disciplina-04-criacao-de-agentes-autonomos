#!/bin/bash

# User settings
USER_NAME="Leonardo Fonseca"
USER_EMAIL="leonardofonsecasilva@hotmail.com"

# Local Git configuration
git config user.name "$USER_NAME"
git config user.email "$USER_EMAIL"

# Display local configurations
echo "Local information:"
git config --local user.name
git config --local user.email

echo ""

# Display global configurations
echo "Global information:"
git config --global user.name
git config --global user.email

read -p "Press any key to continue..."