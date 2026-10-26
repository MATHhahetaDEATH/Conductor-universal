import defaultSettings from '../settings.json';
export interface GlobalState {
  settings?: typeof defaultSettings;
  userInfo?: {
    username?: string;
    name?: string;
    avatar?: string;
    job?: string;
    jobName?: string;
    organization?: string;
    organizationName?: string;
    location?: string;
    locationName?: string;
    email?: string;
    permission_level?: number;
    permission_name?: string;
    permissions: Record<string, string[]>;
  };
  userLoading?: boolean;
}

const initialState: GlobalState = {
  settings: defaultSettings,
  userInfo: {
    permissions: {},
  },
};

export default function store(state = initialState, action) {
  switch (action.type) {
    case 'update-settings': {
      const { settings } = action.payload;
      return {
        ...state,
        settings,
      };
    }
    case 'update-userInfo': {
      const { userInfo = initialState.userInfo, userLoading } = action.payload;
      return {
        ...state,
        userLoading,
        userInfo,
      };
    }
    default:
      return state;
  }
}
