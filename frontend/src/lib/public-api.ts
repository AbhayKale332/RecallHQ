// Anonymous endpoints are scoped by the backend to the synthetic Beacon corpus.
export const PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://recova.indiasouthcentral.cloudapp.azure.com/recallhq/api';

export const SLACK_INSTALL_URL = 'https://recova.indiasouthcentral.cloudapp.azure.com/recallhq/api/slack/install';
export const DEMO_URL = '/workspace/beacon/channel/eng';
export const PUBLIC_BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || '';
