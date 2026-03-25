import { createHashRouter, RouterProvider } from 'react-router-dom';
import WorkflowApp from './WorkflowApp';
import PerformancePrototype from './research/PerformancePrototype';

const router = createHashRouter([
  { path: '/', element: <WorkflowApp /> },
  { path: '/workflow', element: <WorkflowApp /> },
  { path: '/research', element: <PerformancePrototype /> },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
