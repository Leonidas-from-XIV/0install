(* Copyright (C) 2013, Thomas Leonard
 * See the README file for details, or visit http://0install.net.
 *)

(** Keeping track of which keys we trust *)

open General
open Support.Common
module Basedir = Support.Basedir
module U = Support.Utils
module Q = Support.Qdom

module TRUST_NS = struct
  let ns = "http://zero-install.sourceforge.net/2007/injector/trust"
end
module TRUST = Support.Qdom.NsQuery (TRUST_NS)

(** A database of trusted keys. *)
class trust_db config =
  let get_db () =
    (* This is a bit inefficient... (could cache things) *)
    match Basedir.load_first config.system config_trust_db config.basedirs.Basedir.config with
    | None -> StringMap.empty
    | Some path ->
        let root = Q.parse_file config.system path in
        TRUST.fold_left StringMap.empty root "key" ~f:(fun keys key ->
          let domains =
            TRUST.fold_left StringSet.empty key "domain" ~f:(fun map domain ->
              StringSet.add (TRUST.get_attribute "value" domain) map
            ) in
          StringMap.add (TRUST.get_attribute "fingerprint" key) domains keys
        ) in

  let get_domains fingerprint db =
    try StringMap.find fingerprint db
    with Not_found -> StringSet.empty in

  let is_trusted db ~domain fingerprint =
    let domains = get_domains fingerprint db in
    StringSet.mem domain domains || StringSet.mem "*" domains in

  let save db =
    let d = Basedir.save_path config.system (config_site +/ config_prog) config.basedirs.Basedir.config in
    let db_file = d +/ "trustdb.xml" in
    if config.dry_run then (
      Dry_run.log "would update trust database %s" db_file
    ) else (
      let root = TRUST.make_root "trusted-keys" in
      db |> StringMap.iter (fun fingerprint domains ->
        let key = TRUST.insert_first "key" root in
        Q.set_attribute "fingerprint" fingerprint key;
        domains |> StringSet.iter (fun domain ->
          let domain_elem = TRUST.insert_first "domain" key in
          Q.set_attribute "value" domain domain_elem
        );
      );

      config.system#atomic_write [Open_wronly; Open_binary] db_file ~mode:0o644 (fun ch ->
        Q.output (`Channel ch |> Xmlm.make_output) root;
      )
    ) in

  object
    method is_trusted ~domain fingerprint : bool =
      let db = get_db () in
      is_trusted db ~domain fingerprint

    (** Return the set of domains in which this key is trusted.
        If the list includes '*' then the key is trusted everywhere. *)
    method get_trust_domains fingerprint =
      let db = get_db () in
      get_domains fingerprint db

    (** Return the set of keys trusted for this domain. *)
    method get_keys_for_domain domain =
      let db = get_db () in
      let check_key key domains results =
        if StringSet.mem domain domains then StringSet.add key results
        else results in
      StringMap.fold check_key db StringSet.empty

    (* Add key to the list of trusted fingerprints. *)
    method trust_key ~domain fingerprint =
(*
      if domain = "*" then
        log_warning "Calling trust_key() without a domain is deprecated";
*)

      let db = get_db () in
      if not (is_trusted db ~domain fingerprint) then (
        if config.dry_run then
          Dry_run.log "would trust key %s for %s" fingerprint domain
        else (
          (* Ensure fingerprint is valid *)
          let re_fingerprint = Str.regexp "[0-9A-Fa-f]+" in
          assert (Str.string_match re_fingerprint fingerprint 0);

          let domains = get_domains fingerprint db in

          let db = StringMap.add fingerprint (StringSet.add domain domains) db in

          save db
        )
      )

    method untrust_key ~domain fingerprint =
      let db = get_db () in
      if config.dry_run then
        Dry_run.log "would untrust key %s for %s" fingerprint domain
      else (
        let domains = get_domains fingerprint db in
        let domains = StringSet.remove domain domains in
        let db =
          if StringSet.is_empty domains then
            StringMap.remove fingerprint db
          else
            StringMap.add fingerprint domains db in

        save db
      )
  end

let re_domain = Str.regexp "^https?://\\([^/]*@\\)?\\([^*/]+\\)/"

(* Extract the trust domain for a URL. *)
let domain_from_url url =
  if Str.string_match re_domain url 0 then
    Str.matched_group 2 url
  else
    raise_safe "Failed to parse HTTP URL '%s'" url
