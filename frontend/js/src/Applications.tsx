import React, { JSX } from "react";
import { createRoot } from "react-dom/client";
import { gettext } from "./i18n";
import { getPageProps } from "./utils";
import { OAuthScopeDesc } from "./forms/utils";

type ApplicationProps = {
  urlPrefix: string;
  applications: Array<{
    name: string;
    website: string;
    client_id: string;
    client_secret: string;
  }>;
  tokens: Array<{
    name: string;
    website: string;
    scopes: Array<Scope>;
    client_id: string;
  }>;
};

function Applications({
  applications,
  tokens,
  urlPrefix,
}: ApplicationProps): JSX.Element {
  return (
    <>
      <h2>{gettext("Applications")}</h2>

      <div className="clearfix">
        <h3 className="pull-left">{gettext("Your applications")}</h3>
        <a
          href={`${urlPrefix}/client/create`}
          className="btn btn-success pull-right"
          style={{ marginTop: "12px" }}
        >
          <span className="glyphicon glyphicon-plus-sign" />
          {gettext("Create new application")}
        </a>
      </div>
      {applications.length === 0 ? (
        <p className="lead" style={{ textAlign: "center" }}>
          {gettext("No applications found")}
        </p>
      ) : (
        <table className="oauth-applications-table table table-hover">
          <thead>
            <tr>
              <th>{gettext("Name")}</th>
              <th>{gettext("Website")}</th>
              <th>{gettext("Client ID")}</th>
              <th>{gettext("Client secret")}</th>
              <th>{gettext("Actions")}</th>
            </tr>
          </thead>
          <tbody>
            {applications.map((application) => (
              <tr>
                <td>{application.name}</td>
                <td>{application.website}</td>
                <td>{application.client_id}</td>
                <td>{application.client_secret}</td>
                <td>
                  <a
                    className="btn btn-block btn-primary btn-xs"
                    href={`${urlPrefix}/client/edit/${application.client_id}`}
                  >
                    {gettext("Modify")}
                  </a>
                  <a
                    className="btn btn-block btn-danger btn-xs"
                    href={`${urlPrefix}/client/delete/${application.client_id}`}
                  >
                    {gettext("Delete")}
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <hr />

      <h3>{gettext("Authorized applications")}</h3>
      {tokens.length === 0 ? (
        <p className="lead" style={{ textAlign: "center" }}>
          {gettext("No tokens found")}
        </p>
      ) : (
        <table className="oauth-applications-table table table-hover">
          <thead>
            <tr>
              <th>{gettext("Name")}</th>
              <th>{gettext("Website")}</th>
              <th>{gettext("Access")}</th>
              <th>{gettext("Actions")}</th>
            </tr>
          </thead>
          <tbody>
            {tokens.map((token) => (
              <tr>
                <td>
                  <b>{token.name}</b>
                </td>
                <td>{token.website}</td>
                <td>{OAuthScopeDesc(token.scopes)}</td>
                <td>
                  <form
                    action={`${urlPrefix}/client/${token.client_id}/revoke/user`}
                    method="post"
                    className="btn btn-danger btn-xs"
                  >
                    <button
                      type="submit"
                      className="btn btn-danger"
                      style={{ color: "white" }}
                    >
                      {gettext("Revoke access")}
                    </button>
                  </form>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

document.addEventListener("DOMContentLoaded", () => {
  const { domContainer, reactProps, globalProps } = getPageProps();
  const { applications, tokens } = reactProps;
  const { url_prefix } = globalProps;

  const renderRoot = createRoot(domContainer!);
  renderRoot.render(
    <Applications
      applications={applications}
      tokens={tokens}
      urlPrefix={url_prefix}
    />
  );
});
