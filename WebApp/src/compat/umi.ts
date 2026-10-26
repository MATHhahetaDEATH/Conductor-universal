import { createHashHistory, createBrowserHistory } from 'history';

// Use browser history as default, or hash if needed
export const history = createBrowserHistory();

export default {
  history,
};
